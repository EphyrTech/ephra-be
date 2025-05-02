from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from typing import Dict, List, Optional
import json
import asyncio
from datetime import datetime
from jose import JWTError, jwt

from app.core.config import settings
from app.db.database import get_db
from app.db.models import User
from sqlalchemy.orm import Session

router = APIRouter()

# Store active connections
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        print(f"User {user_id} connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
            print(f"User {user_id} disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                await connection.send_text(message)
    
    async def broadcast(self, message: str):
        for user_id in self.active_connections:
            await self.send_personal_message(message, user_id)

manager = ConnectionManager()

# WebSocket authentication dependency
async def get_current_user_ws(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> User:
    try:
        # Get token from query parameters
        token = websocket.query_params.get("token")
        if token is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        
        # Decode token
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        
        if not user.is_active:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Inactive user",
            )
        
        return user
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
):
    """
    WebSocket endpoint for real-time communication.
    
    Requires authentication via a token query parameter.
    Example: ws://localhost:8000/v1/ws?token=your_jwt_token
    
    Messages should be JSON with a "type" field indicating the message type.
    """
    # Authenticate user
    try:
        user = await get_current_user_ws(websocket, db)
        await manager.connect(websocket, user.id)
        
        # Send welcome message
        await websocket.send_json({
            "type": "welcome",
            "message": f"Welcome, {user.name}!",
            "timestamp": datetime.now().isoformat()
        })
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_text()
                
                try:
                    # Parse JSON message
                    message = json.loads(data)
                    
                    # Process message based on type
                    if "type" not in message:
                        await websocket.send_json({
                            "type": "error",
                            "message": "Message must have a 'type' field",
                            "timestamp": datetime.now().isoformat()
                        })
                        continue
                    
                    # Echo message back to user
                    if message["type"] == "echo":
                        await websocket.send_json({
                            "type": "echo",
                            "message": message.get("message", ""),
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Broadcast message to all users
                    elif message["type"] == "broadcast":
                        if "message" in message:
                            broadcast_msg = json.dumps({
                                "type": "broadcast",
                                "user": user.name,
                                "message": message["message"],
                                "timestamp": datetime.now().isoformat()
                            })
                            await manager.broadcast(broadcast_msg)
                    
                    # Unknown message type
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unknown message type: {message['type']}",
                            "timestamp": datetime.now().isoformat()
                        })
                
                except json.JSONDecodeError:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid JSON",
                        "timestamp": datetime.now().isoformat()
                    })
        
        except WebSocketDisconnect:
            manager.disconnect(websocket, user.id)
    
    except HTTPException:
        # Authentication failed
        try:
            await websocket.close()
        except:
            pass

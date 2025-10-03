from app.services.logto_service import LogtoUserManager
from app.db.models import User, UserRole
from app.core.config import settings
from app.core.logging import get_logger
from typing import Optional
from psycopg2 import IntegrityError, sql


logger = get_logger(__name__)


class BaseUser:

    def __init__(
            self, 
            db, 
            logto_user_manager: LogtoUserManager,
            log_to_user_id: Optional[str] = None,
            db_user_id: Optional[str] = None

        ):
        self.db = db
        self.logto_user_manager = logto_user_manager
        self.log_to_user_id = log_to_user_id
        self.db_user_id = db_user_id
        self.current_logto_user = None
        self.current_db_user = None
        self.db_user_role = UserRole.USER
        self.logto_user_role = settings.roles_map[UserRole.USER.value]['logto_role']
        self.logto_user_role_id = settings.roles_map[UserRole.USER.value]['logto_id']
        self.logto_user_email = None
        self.db_user_email = None
    

    async def init(self):
        if not self.log_to_user_id:
            self.current_db_user = self.db.query(User).filter(User.id == self.db_user_id).first()
            self.log_to_user_id = self.current_db_user.logto_user_id
        else:
            self.current_db_user = self.db.query(User).filter(User.logto_user_id == self.log_to_user_id).first()
        
        self.current_logto_user = await self.logto_user_manager.get(self.log_to_user_id)
        same_email_users = self.db.query(User).filter(User.email == self.current_logto_user.primaryEmail).all()

        if len(same_email_users) > 1:
            raise Exception(f"Multiple users with same email: {self.current_logto_user.primaryEmail}")
        
        if not self.current_db_user and same_email_users:
            self.current_db_user = same_email_users[0]
    
        if not self.current_logto_user:
            raise Exception(f"User not found in logto: {self.log_to_user_id}")
        user_roles = await self.logto_user_manager.get_roles(self.log_to_user_id)
        logto_user_role = [r for r in user_roles if r.isDefault][-1]
        
        assert logto_user_role.name == self.logto_user_role, \
        f"User role in logto is {logto_user_role.name}, but expected {self.logto_user_role}"
        
    
    async def upsert_db_user(self):
        try:
            logto_data = {
                "email": self.current_logto_user.primaryEmail,
                "logto_user_id": self.log_to_user_id,
                "role": self.db_user_role,
                "name": getattr(self.current_logto_user, "name", "NoName Persona"),
                "is_active": not self.current_logto_user.isSuspended,
                "photo_url": self.current_logto_user.avatar,
            }        
            
            if not self.current_db_user:
                logger.info(f"Creating new user in db for logto user {self.log_to_user_id}")
                db_user = User(**logto_data)
                self.db.add(db_user)
                self.db.commit()
                self.db.refresh(db_user)
                logger.info(f"User created in db: {db_user.id}")
            else:
                logger.info(f"Updating user in db for logto user {self.log_to_user_id}")
                db_user = self.current_db_user
                updates_needed = False
                
                # Dictionary to track changes for logging
                changed_fields = {}

                # Iterate through the Logto data and compare against the DB user object
                for key, new_value in logto_data.items():
                    
                    # Retrieve the current value from the DB user
                    current_value = getattr(db_user, key, None)

                    # Skip comparison for fields we don't want to sync or update 
                    # (e.g., primary key, creation date, etc.)
                    if key in ["hashed_password"]:
                        continue

                    # IMPORTANT: Compare the values. Since Python objects (like enums/classes)
                    # handle inequality correctly, this comparison should work.
                    if current_value != new_value:
                        # Data mismatch found, update the attribute
                        setattr(db_user, key, new_value)
                        changed_fields[key] = new_value
                        updates_needed = True

                if updates_needed:
                    self.db.commit()
                    logger.info(f"User updated in db: {db_user.id}. Changed fields: {changed_fields}")

            self.current_db_user = db_user
            return True
        except IntegrityError as e:
            logger.error(f"Integrity error while creating user: {e}")            
            if "duplicate key value violates unique constraint" in str(e):
                logger.error(f"Duplicate while creating user: {e}")
                
        except Exception as e:
            logger.error(f"Exception while creating user: {e}")
        
        self.db.rollback()

        return False

    async def update_user_role(self, new_role: UserRole):
        try:
            logger.info(f"Updating user {self.log_to_user_id} role to {new_role}")
            await self.logto_user_manager.update_roles(
                user_id=self.log_to_user_id,
                role_ids=[settings.roles_map[new_role]['logto_id']]
                )
            logger.info(f"User {self.log_to_user_id} role updated to {new_role}")
        except Exception as e:
            logger.error(f"Unable to change role for {self.log_to_user_id}: {e}")
            raise Exception(f"Unable to change role for {self.log_to_user_id}")
        

        db_user = self.current_db_user
        setattr(db_user, "role", new_role)
        self.db.commit()
        return True
        
    async def suspend(self):
        try:
            self.current_db_user.is_active = False
            self.db.commit()
            self.db.refresh(self.current_db_user)
            logger.info(f"User {self.current_db_user.id} suspended in db")

            await self.logto_user_manager.suspend(user_id=self.log_to_user_id)
            logger.info(f"User {self.log_to_user_id} suspended in logto")
            return True
        
        except Exception as e:
            logger.error(f"Exception while suspending user: {e}")
            self.db.rollback()
            return False



class CareProviderUser(BaseUser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_user_role = UserRole.CARE_PROVIDER
        self.logto_user_role = settings.roles_map[UserRole.CARE_PROVIDER]['logto_role']
        self.logto_user_role_id = settings.roles_map[UserRole.CARE_PROVIDER]['logto_id']

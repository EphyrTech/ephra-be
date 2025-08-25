import pytest


def test_get_journals(authorized_client, test_journal):
    # Test getting all journals
    response = authorized_client.get("/v1/journals")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["id"] == test_journal.id
    assert data[0]["title"] == test_journal.title
    assert data[0]["content"] == test_journal.content


def test_get_journals_unauthorized(client):
    # Test getting journals without authentication
    response = client.get("/v1/journals")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_create_journal(authorized_client, test_user):
    # Test creating a new journal
    response = authorized_client.post(
        "/v1/journals",
        json={
            "title": "New Journal",
            "content": "This is a new journal entry."
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "New Journal"
    assert data["content"] == "This is a new journal entry."
    assert data["user_id"] == test_user.id


def test_create_journal_unauthorized(client):
    # Test creating a journal without authentication
    response = client.post(
        "/v1/journals",
        json={
            "title": "New Journal",
            "content": "This is a new journal entry."
        }
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_get_journal(authorized_client, test_journal):
    # Test getting a specific journal
    response = authorized_client.get(f"/v1/journals/{test_journal.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_journal.id
    assert data["title"] == test_journal.title
    assert data["content"] == test_journal.content


def test_get_journal_not_found(authorized_client):
    # Test getting a non-existent journal
    response = authorized_client.get("/v1/journals/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_get_journal_unauthorized(client, test_journal):
    # Test getting a journal without authentication
    response = client.get(f"/v1/journals/{test_journal.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_update_journal(authorized_client, test_journal, db):
    # Test updating a journal
    response = authorized_client.put(
        f"/v1/journals/{test_journal.id}",
        json={
            "title": "Updated Journal",
            "content": "This journal has been updated."
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_journal.id
    assert data["title"] == "Updated Journal"
    assert data["content"] == "This journal has been updated."
    
    # Verify the database was updated
    db.refresh(test_journal)
    assert test_journal.title == "Updated Journal"
    assert test_journal.content == "This journal has been updated."


def test_update_journal_partial(authorized_client, test_journal, db):
    # Test partial update of a journal
    response = authorized_client.put(
        f"/v1/journals/{test_journal.id}",
        json={
            "title": "Partially Updated Journal"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == test_journal.id
    assert data["title"] == "Partially Updated Journal"
    assert data["content"] == test_journal.content  # Content should remain unchanged
    
    # Verify the database was updated
    db.refresh(test_journal)
    assert test_journal.title == "Partially Updated Journal"


def test_update_journal_not_found(authorized_client):
    # Test updating a non-existent journal
    response = authorized_client.put(
        "/v1/journals/nonexistent-id",
        json={
            "title": "Updated Journal"
        }
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_update_journal_unauthorized(client, test_journal):
    # Test updating a journal without authentication
    response = client.put(
        f"/v1/journals/{test_journal.id}",
        json={
            "title": "Updated Journal"
        }
    )
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()


def test_delete_journal(authorized_client, test_journal, db):
    # Test deleting a journal
    response = authorized_client.delete(f"/v1/journals/{test_journal.id}")
    assert response.status_code == 204
    
    # Verify the journal was deleted from the database
    journal = db.query(test_journal.__class__).filter_by(id=test_journal.id).first()
    assert journal is None


def test_delete_journal_not_found(authorized_client):
    # Test deleting a non-existent journal
    response = authorized_client.delete("/v1/journals/nonexistent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_delete_journal_unauthorized(client, test_journal):
    # Test deleting a journal without authentication
    response = client.delete(f"/v1/journals/{test_journal.id}")
    assert response.status_code == 401
    assert "not authenticated" in response.json()["detail"].lower()

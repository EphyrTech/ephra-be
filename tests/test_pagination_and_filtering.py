import pytest
from fastapi import status


def test_journal_pagination(authorized_client, multiple_journals, pagination_params):
    """Test pagination of journal entries"""
    response = authorized_client.get(
        f"/v1/journals?skip={pagination_params['skip']}&limit={pagination_params['limit']}"
    )
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    
    # Check that we got the expected number of results
    expected_count = min(pagination_params["limit"], 15 - pagination_params["skip"])
    if expected_count > 0:
        assert len(data) == expected_count
    else:
        assert len(data) == 0


def test_specialist_pagination(authorized_client, multiple_specialists, pagination_params):
    """Test pagination of specialists"""
    response = authorized_client.get(
        f"/v1/care-providers?skip={pagination_params['skip']}&limit={pagination_params['limit']}"
    )
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    
    # Check that we got the expected number of results
    expected_count = min(pagination_params["limit"], 10 - pagination_params["skip"])
    if expected_count > 0:
        assert len(data) == expected_count
    else:
        assert len(data) == 0


def test_appointment_pagination(authorized_client, multiple_appointments, pagination_params):
    """Test pagination of appointments"""
    response = authorized_client.get(
        f"/v1/appointments?skip={pagination_params['skip']}&limit={pagination_params['limit']}"
    )
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    
    # Check that we got the expected number of results
    expected_count = min(pagination_params["limit"], 5 - pagination_params["skip"])
    if expected_count > 0:
        assert len(data) == expected_count
    else:
        assert len(data) == 0


def test_journal_search(authorized_client, multiple_journals, search_query):
    """Test searching journal entries"""
    response = authorized_client.get(f"/v1/journals?search={search_query['query']}")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    
    # If searching for "test" or "journal", we should get results
    if search_query["query"] in ["test", "journal"]:
        assert len(data) > 0
        # Check that each result contains the search term
        for journal in data:
            assert (
                search_query["query"].lower() in journal["title"].lower() or 
                search_query["query"].lower() in journal["content"].lower()
            )
    # If searching for "nonexistent", we should get no results
    elif search_query["query"] == "nonexistent":
        assert len(data) == 0


def test_specialist_filter_by_type(authorized_client, multiple_specialists):
    """Test filtering specialists by type"""
    # Test filtering by mental health specialists
    response = authorized_client.get("/v1/care-providers?type=mental")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check that all returned specialists are mental health specialists
    for specialist in data:
        assert specialist["specialist_type"] == "mental"
    
    # Test filtering by physical health specialists
    response = authorized_client.get("/v1/care-providers?type=physical")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    
    # Check that all returned specialists are physical health specialists
    for specialist in data:
        assert specialist["specialist_type"] == "physical"


def test_appointment_filter_by_date_range(authorized_client, multiple_appointments, date_range):
    """Test filtering appointments by date range"""
    response = authorized_client.get(
        f"/v1/appointments?start_date={date_range['start_date']}&end_date={date_range['end_date']}"
    )
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    
    # Check that all returned appointments are within the date range
    for appointment in data:
        appointment_start = appointment["start_time"]
        assert date_range["start_date"] <= appointment_start <= date_range["end_date"]


def test_appointment_filter_by_status(authorized_client, multiple_appointments):
    """Test filtering appointments by status"""
    # First, update one appointment to be confirmed
    appointment_id = multiple_appointments[0].id
    response = authorized_client.put(
        f"/v1/appointments/{appointment_id}",
        json={"status": "confirmed"}
    )
    assert response.status_code == status.HTTP_200_OK
    
    # Test filtering by pending status
    response = authorized_client.get("/v1/appointments?status=pending")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 4  # We should have 4 pending appointments
    
    # Check that all returned appointments have pending status
    for appointment in data:
        assert appointment["status"] == "pending"
    
    # Test filtering by confirmed status
    response = authorized_client.get("/v1/appointments?status=confirmed")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1  # We should have 1 confirmed appointment
    
    # Check that all returned appointments have confirmed status
    for appointment in data:
        assert appointment["status"] == "confirmed"

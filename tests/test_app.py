from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from src.app import activities, app


@pytest.fixture
def client():
    original_activities = deepcopy(activities)
    with TestClient(app) as test_client:
        yield test_client
    activities.clear()
    activities.update(original_activities)


def test_root_redirects_to_website(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"
    assert client.get(response.headers["location"]).status_code == 200


def test_get_activities_includes_new_options(client):
    expected_names = {
        "Chess Club", "Programming Class", "Gym Class",
        "Soccer Team", "Basketball Team", "Art Club",
        "Drama Club", "Debate Club", "Science Club",
    }

    response = client.get("/activities")

    assert response.status_code == 200
    assert set(response.json()) == expected_names
    for activity in response.json().values():
        assert activity["description"]
        assert activity["schedule"]
        assert activity["max_participants"] > 0
        assert isinstance(activity["participants"], list)


def test_signup_adds_participant(client):
    email = "new@mergington.edu"
    before = client.get("/activities").json()["Chess Club"]["participants"]

    response = client.post("/activities/Chess Club/signup", params={"email": email})

    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == before + [email]


def test_duplicate_signup_does_not_change_participants(client):
    before = client.get("/activities").json()["Chess Club"]["participants"]

    response = client.post("/activities/Chess Club/signup", params={"email": before[0]})

    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up"
    assert client.get("/activities").json()["Chess Club"]["participants"] == before


def test_student_can_join_multiple_activities(client):
    email = activities["Chess Club"]["participants"][0]

    response = client.post("/activities/Art Club/signup", params={"email": email})

    assert response.status_code == 200
    assert email in client.get("/activities").json()["Art Club"]["participants"]
    assert email in client.get("/activities").json()["Chess Club"]["participants"]


def test_unregister_removes_only_selected_participant_and_allows_rejoining(client):
    before = client.get("/activities").json()["Chess Club"]["participants"]
    email = before[0]

    response = client.delete("/activities/Chess Club/unregister", params={"email": email})

    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert client.get("/activities").json()["Chess Club"]["participants"] == before[1:]
    assert client.post("/activities/Chess Club/signup", params={"email": email}).status_code == 200


def test_unregister_missing_participant_does_not_change_data(client):
    before = client.get("/activities").json()

    response = client.delete(
        "/activities/Chess Club/unregister", params={"email": "missing@mergington.edu"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Student not registered"
    assert client.get("/activities").json() == before


@pytest.mark.parametrize("method, action", [("post", "signup"), ("delete", "unregister")])
def test_unknown_activity_returns_not_found(client, method, action):
    before = client.get("/activities").json()

    response = getattr(client, method)(
        f"/activities/Missing Club/{action}", params={"email": "new@mergington.edu"}
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"
    assert client.get("/activities").json() == before


@pytest.mark.parametrize("method, action", [("post", "signup"), ("delete", "unregister")])
def test_email_is_required(client, method, action):
    before = client.get("/activities").json()

    response = getattr(client, method)(f"/activities/Chess Club/{action}")

    assert response.status_code == 422
    assert client.get("/activities").json() == before

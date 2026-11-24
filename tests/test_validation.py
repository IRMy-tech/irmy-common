import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from irmy_common.exceptions import register_exceptions_handler
from irmy_common.validation import Tags, TimeZoneName, key_str, name_str, text_str


class Model(BaseModel):
    name: name_str(8)
    description: text_str(5) | None = None
    required_text: text_str(5, required=True) | None = None
    tags: Tags | None = None
    tz: TimeZoneName | None = None
    key: key_str(4) | None = None


def test_values_are_trimmed():
    model = Model(name="  my app ", description="  ab  ", tags={" team ": "  billing "})
    assert model.name == "my app"
    assert model.description == "ab"
    assert model.tags == {"team": "billing"}


@pytest.mark.parametrize("data, field", [
    ({"name": "   "}, "name"),                              # whitespace only -> empty after trim
    ({"name": ""}, "name"),
    ({"name": "bad!"}, "name"),
    ({"name": "too-long-x"}, "name"),
    ({"name": "a", "description": "123456"}, "description"),
    ({"name": "a", "required_text": "   "}, "required_text"),
    ({"name": "a", "tags": {"a b": "v"}}, "tags"),
    ({"name": "a", "tags": {"k" * 65: "v"}}, "tags"),
    ({"name": "a", "tags": {"k": "v" * 257}}, "tags"),
    ({"name": "a", "tags": {f"k{i}": "v" for i in range(11)}}, "tags"),
    ({"name": "a", "tz": "Mars/Olympus"}, "tz"),
    ({"name": "a", "key": "a-b c"}, "key"),
])
def test_invalid_values(data, field):
    with pytest.raises(ValidationError) as e:
        Model(**data)
    assert e.value.errors()[0]["loc"][0] == field


def test_valid_edge_values():
    model = Model(name="A-b_ 9", description="", tags={f"k{i}": "" for i in range(10)},
                  tz="Europe/Kyiv", key="a_-1")
    assert model.description == "" and len(model.tags) == 10


def test_constraints_are_in_the_json_schema():
    props = Model.model_json_schema()["properties"]
    assert props["name"] == {"maxLength": 8, "minLength": 1, "pattern": r"^[A-Za-z0-9_\- ]+$",
                             "title": "Name", "type": "string"}
    tags = props["tags"]["anyOf"][0]
    assert tags["maxProperties"] == 10
    assert tags["propertyNames"]["maxLength"] == 64


def test_violation_is_a_400_with_details():
    app = FastAPI()
    register_exceptions_handler(app)

    @app.post("/things")
    async def create(body: Model):
        return {}

    response = TestClient(app).post("/things", json={"name": "   "})
    assert response.status_code == 400
    assert response.json() == {"error": "Validation failed",
                               "details": [{"field": "name", "message": "String should have at least 1 character"}]}


class TextModel(BaseModel):
    text: text_str(32)
    tags: Tags | None = None


def test_nul_and_lone_surrogates_are_stored_as_escape_text():
    assert TextModel(text="x\x00y").text == "x\\u0000y"
    assert TextModel(text="a", tags={"k": "\ud800"}).tags == {"k": "\\ud800"}


def test_escape_text_counts_in_the_length():
    with pytest.raises(ValidationError):
        Model(name="a", description="\x00")          # 6 characters once written out, limit is 5


def test_storable_walks_json_like_values():
    from irmy_common.validation import storable
    body = {"a\x00": ["b\x00", 1, None, {"c": "\udfff"}], "n": 2.5, "ok": "plain é \U0001F600"}
    assert storable(body) == {"a\\u0000": ["b\\u0000", 1, None, {"c": "\\udfff"}], "n": 2.5,
                              "ok": "plain é \U0001F600"}
    for value in storable(body).values():
        str(value).encode("utf-8")                   # everything is UTF-8 encodable now


def test_storable_text_through_the_api_is_saved_not_rejected():
    app = FastAPI()
    register_exceptions_handler(app)

    @app.post("/things")
    async def create(body: TextModel):
        return {"text": body.text}

    response = TestClient(app).post("/things", content='{"text": "a\\u0000b"}',
                                    headers={"content-type": "application/json"})
    assert response.status_code == 200
    assert response.json() == {"text": "a\\u0000b"}

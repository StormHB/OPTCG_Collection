"""Korak 11B.3: regresijski testovi generiranog OpenAPI ugovora."""

from app.main import create_app


def _schema() -> dict:
    return create_app().openapi()


def _parameter(operation: dict, name: str) -> dict:
    return next(item for item in operation["parameters"] if item["name"] == name)


def _json_schema(operation: dict, status: int) -> dict:
    return operation["responses"][str(status)]["content"]["application/json"]["schema"]


def test_openapi_contains_exact_application_route_inventory():
    schema = _schema()
    actual = {
        (method.upper(), path)
        for path, path_item in schema["paths"].items()
        for method in path_item
        if method in {"get", "post", "patch", "delete", "put"}
    }
    expected = {
        ("GET", "/health"),
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/refresh"),
        ("GET", "/auth/me"),
        ("GET", "/admin/users"),
        ("GET", "/cards"),
        ("GET", "/cards/filters"),
        ("GET", "/cards/{card_id}"),
        ("GET", "/collections/{user_id}"),
        ("GET", "/collections/{user_id}/stats"),
        ("POST", "/collections/{user_id}/entries"),
        ("PATCH", "/collections/{user_id}/entries/{printing_id}"),
        ("DELETE", "/collections/{user_id}/entries/{printing_id}"),
        ("POST", "/collections/{user_id}/import/preview"),
        ("POST", "/collections/{user_id}/import/apply"),
        ("GET", "/collections/{user_id}/loans"),
        ("POST", "/collections/{user_id}/loans"),
        ("GET", "/collections/{user_id}/loans/{loan_id}"),
        ("POST", "/collections/{user_id}/loans/{loan_id}/returns"),
    }
    assert actual == expected


def test_swagger_bearer_scheme_and_public_private_routes_are_documented():
    schema = _schema()
    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }

    public = {
        ("get", "/health"),
        ("post", "/auth/register"),
        ("post", "/auth/login"),
        ("post", "/auth/refresh"),
        ("get", "/cards/filters"),
        ("get", "/cards/{card_id}"),
    }
    for method, path in public:
        assert "security" not in schema["paths"][path][method]

    assert schema["paths"]["/cards"]["get"]["security"] == [
        {},
        {"HTTPBearer": []},
    ]

    protected = {
        ("get", "/auth/me"),
        ("get", "/admin/users"),
        ("get", "/collections/{user_id}"),
        ("get", "/collections/{user_id}/stats"),
        ("post", "/collections/{user_id}/entries"),
        ("patch", "/collections/{user_id}/entries/{printing_id}"),
        ("delete", "/collections/{user_id}/entries/{printing_id}"),
        ("post", "/collections/{user_id}/import/preview"),
        ("post", "/collections/{user_id}/import/apply"),
        ("get", "/collections/{user_id}/loans"),
        ("post", "/collections/{user_id}/loans"),
        ("get", "/collections/{user_id}/loans/{loan_id}"),
        ("post", "/collections/{user_id}/loans/{loan_id}/returns"),
    }
    for method, path in protected:
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]


def test_declared_success_and_error_statuses_match_http_contract():
    schema = _schema()
    expected = {
        ("get", "/health"): {200},
        ("post", "/auth/register"): {201, 409, 422},
        ("post", "/auth/login"): {200, 401, 422},
        ("post", "/auth/refresh"): {200, 401, 422},
        ("get", "/auth/me"): {200, 401},
        ("get", "/admin/users"): {200, 401, 403, 422},
        ("get", "/cards"): {200, 401, 422},
        ("get", "/cards/filters"): {200},
        ("get", "/cards/{card_id}"): {200, 404, 422},
        ("get", "/collections/{user_id}"): {200, 401, 403, 422},
        ("get", "/collections/{user_id}/stats"): {200, 401, 403, 422},
        ("post", "/collections/{user_id}/entries"): {
            201,
            401,
            403,
            404,
            409,
            422,
        },
        ("patch", "/collections/{user_id}/entries/{printing_id}"): {
            200,
            401,
            403,
            404,
            409,
            422,
        },
        ("delete", "/collections/{user_id}/entries/{printing_id}"): {
            204,
            401,
            403,
            404,
            409,
            422,
        },
        ("post", "/collections/{user_id}/import/preview"): {
            200,
            401,
            403,
            413,
            422,
        },
        ("post", "/collections/{user_id}/import/apply"): {
            200,
            401,
            403,
            409,
            413,
            422,
        },
        ("get", "/collections/{user_id}/loans"): {200, 401, 403, 422},
        ("post", "/collections/{user_id}/loans"): {
            201,
            401,
            403,
            404,
            409,
            422,
        },
        ("get", "/collections/{user_id}/loans/{loan_id}"): {
            200,
            401,
            403,
            404,
            422,
        },
        ("post", "/collections/{user_id}/loans/{loan_id}/returns"): {
            200,
            401,
            403,
            404,
            409,
            422,
        },
    }
    for (method, path), statuses in expected.items():
        actual = {int(status) for status in schema["paths"][path][method]["responses"]}
        assert actual == statuses, (method, path, actual)


def test_controlled_error_and_validation_error_schemas_match_runtime_shape():
    schema = _schema()
    components = schema["components"]["schemas"]
    assert components["ApiErrorResponse"]["required"] == ["code", "message"]
    assert components["ValidationErrorResponse"]["required"] == [
        "code",
        "message",
        "errors",
    ]
    assert components["ValidationIssueResponse"]["required"] == ["field", "message"]

    operation = schema["paths"]["/auth/login"]["post"]
    assert _json_schema(operation, 401)["$ref"].endswith("/ApiErrorResponse")
    validation = _json_schema(operation, 422)
    refs = {item["$ref"].rsplit("/", 1)[-1] for item in validation["anyOf"]}
    assert refs == {"ApiErrorResponse", "ValidationErrorResponse"}


def test_card_filter_enums_ranges_and_personal_filter_description():
    operation = _schema()["paths"]["/cards"]["get"]
    costs = _parameter(operation, "costs")["schema"]["anyOf"][0]["items"]
    powers = _parameter(operation, "powers")["schema"]["anyOf"][0]["items"]
    counters = _parameter(operation, "counter_values")["schema"]["anyOf"][0]["items"]
    missing = _parameter(operation, "counter_missing")
    statuses = _parameter(operation, "collection_status")

    assert (costs["minimum"], costs["maximum"]) == (0, 10)
    assert (powers["minimum"], powers["maximum"]) == (0, 13_000)
    assert counters["enum"] == ["0", "1000", "2000"]
    assert missing["schema"]["anyOf"][0]["type"] == "boolean"
    assert "SQL NULL" in missing["description"]
    assert statuses["schema"]["anyOf"][0]["items"]["enum"] == [
        "owned",
        "missing",
        "playset",
    ]
    assert "JWT access token" in statuses["description"]


def test_excel_routes_document_multipart_modes_plan_token_and_responses():
    schema = _schema()
    preview = schema["paths"]["/collections/{user_id}/import/preview"]["post"]
    apply = schema["paths"]["/collections/{user_id}/import/apply"]["post"]

    for operation in (preview, apply):
        assert "multipart/form-data" in operation["requestBody"]["content"]
        assert _parameter(operation, "mode")["schema"]["enum"] == ["replace", "add"]

    token = _parameter(apply, "plan_token")
    assert token["required"] is True
    assert token["schema"]["minLength"] == token["schema"]["maxLength"] == 64
    assert token["schema"]["pattern"] == "^[0-9a-f]{64}$"
    assert "nije JWT" in token["description"]
    assert "nema vremenski rok" in token["description"]

    assert _json_schema(preview, 200)["$ref"].endswith(
        "/CollectionImportPreviewResponse"
    )
    assert _json_schema(apply, 200)["$ref"].endswith("/CollectionImportApplyResponse")


def test_request_models_examples_boundaries_and_timezone_contract():
    components = _schema()["components"]["schemas"]
    for name in (
        "RegisterRequest",
        "LoginRequest",
        "RefreshRequest",
        "CollectionEntryCreate",
        "CollectionEntryUpdate",
        "CardLoanCreate",
        "CardLoanReturn",
    ):
        assert "example" in components[name]

    create = components["CardLoanCreate"]["properties"]
    returned = components["CardLoanReturn"]["properties"]
    assert (create["quantity"]["minimum"], create["quantity"]["maximum"]) == (
        1,
        999_999,
    )
    assert create["direction"]["enum"] == ["lent", "borrowed"]
    assert (returned["quantity"]["minimum"], returned["quantity"]["maximum"]) == (
        1,
        999_999,
    )
    for field in (create["loaned_at"], create["due_at"], returned["returned_at"]):
        date_schema = field["anyOf"][0]
        assert date_schema["format"] == "date-time"
        assert "obaveznom vremenskom zonom" in date_schema["description"]


def test_loan_list_filters_and_response_identifiers_are_documented():
    schema = _schema()
    operation = schema["paths"]["/collections/{user_id}/loans"]["get"]
    direction = _parameter(operation, "direction")["schema"]["anyOf"][0]
    active_only = _parameter(operation, "active_only")["schema"]
    response = schema["components"]["schemas"]["CardLoanResponse"]

    assert direction["enum"] == ["lent", "borrowed"]
    assert active_only == {"type": "boolean", "default": False, "title": "Active Only"}
    assert {
        "printing_id",
        "card_code",
        "card_name",
        "set_code",
        "variant_code",
        "outstanding_quantity",
    } <= set(response["required"])

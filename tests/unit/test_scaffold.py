import app


def test_backend_package_is_importable():
    assert app.__doc__ == "Insurance claims SOP harness backend."

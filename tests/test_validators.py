from cli_wrapper.validators import Validator, validators


class TestValidators:
    def test_validator(self):
        v = Validator("is_alnum")
        assert v("abc123") is True
        assert v("abc123!") is False

        validators.register_group("test_validators_group")

        validators.register("is_pod1", lambda x: x == "pod1", group="test_validators_group")
        v = Validator("test_validators_group.is_pod1")
        assert v("pod1") is True
        assert v("pod2") is False

        validators.register("is_equal", lambda x, y: x == y, group="test_validators_group")
        v = Validator({"test_validators_group.is_equal": "pod1"})
        assert v("pod1") is True
        assert v("pod2") is False

        def is_equal(x, y, case_sensitive=True):
            return x == y if case_sensitive else x.lower() == y.lower()

        validators._all["test_validators_group"]["is_equal"] = is_equal
        v = Validator({"test_validators_group.is_equal": {"args": "pod1", "case_sensitive": False}})
        assert v("pod1") is True
        assert v("POD1") is True

        validators._all.pop("test_validators_group")

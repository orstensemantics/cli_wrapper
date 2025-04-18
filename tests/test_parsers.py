import pytest

from cli_wrapper.parsers import Parser, parsers


class TestParsers:
    def test_parser(self):
        testdata = '{"foo": {"bar": "baz"}}'

        # simple string parser
        parser = Parser("json")
        assert parser(testdata) == {"foo": {"bar": "baz"}}

        # list of parsers
        parser = Parser(["json", {"extract": ["foo"]}])
        assert parser(testdata) == {"bar": "baz"}

        # list of parsers with custom function
        def custom_extract(src):
            return src["foo"]["bar"]

        parser = Parser(["json", custom_extract])
        assert parser(testdata) == "baz"

        testdata = "foo:\n  bar: baz\n"
        parser = Parser(["yaml", "dotted_dict"])
        assert parser(testdata).foo.bar == "baz"

        # single parser with params
        testdata = {"foo": {"bar": "baz"}}
        parser = Parser({"extract": ["foo"]})
        assert parser(testdata) == {"bar": "baz"}

        # custom function with params
        def extract_with_params(src, *args, **kwargs):
            return src[args[0]][kwargs["key"]]

        parser = Parser({extract_with_params: {"args": ["foo"], "key": "bar"}})
        assert parser(testdata) == "baz"

        with pytest.raises(KeyError):
            parser = Parser("non_existing_parser")
            parser(testdata)

    def test_weird_cases(self):
        testdata = '"1"'
        parser = Parser(["json", "dotted_dict"])
        assert parser(testdata) == "1"

        testdata = "[1, 2, 3]"
        assert parser(testdata) == [1, 2, 3]
        testdata = '[1, {"foo": "bar"}]'
        p = parser(testdata)
        assert p[0] == 1
        assert p[1].foo == "bar"

    def test_parsers_register(self):
        def custom_parser(src):
            return src["foo"]["bar"]

        parsers.register("custom_parser", custom_parser)
        parser = Parser(["json", "custom_parser"])
        testdata = '{"foo": {"bar": "baz"}}'
        assert parser(testdata) == "baz"

        # Test for duplicate parser registration
        with pytest.raises(KeyError):
            parsers.register("custom_parser", custom_parser)

    def test_parsers_register_group(self):
        def custom_parser(src):
            return src["foo"]["bar"]

        parsers.register_group("custom_group", {"custom_parser": custom_parser})
        parser = Parser(["json", "custom_group.custom_parser"])
        testdata = '{"foo": {"bar": "baz"}}'
        assert parser(testdata) == "baz"

        # Test for duplicate parser group registration
        with pytest.raises(KeyError):
            parsers.register_group("custom_group", {"custom_parser": custom_parser})

    def test_parser_registration_errors(self):
        def custom_parser(src):
            return src["foo"]["bar"]

        with pytest.raises(KeyError):
            parsers.register("custom.parser", custom_parser)

        with pytest.raises(KeyError):
            parsers.register_group("custom.group", {"custom_parser": custom_parser})

        with pytest.raises(KeyError):
            parsers.register_group("custom_group", {"custom.parser": custom_parser})

    def test_get_parser_errors(self):
        with pytest.raises(KeyError):
            parsers.get("non_existing_parser")
        with pytest.raises(KeyError):
            parsers.get("non_existing_group.non_existing_parser")
        try:
            parsers.register_group("custom_group", {"custom_parser": lambda x: x})
        except KeyError:
            pass
        with pytest.raises(KeyError):
            parsers.get("custom_group.non_existing_parser")
        with pytest.raises(KeyError):
            parsers.get("too.many.dots.in.name")

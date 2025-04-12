from cli_wrapper.parsers import Parser


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

        testdata = (
            "foo:\n"
            "  bar: baz\n"
        )
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
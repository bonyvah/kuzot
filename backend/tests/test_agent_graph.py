from langchain_core.messages import AIMessage

from app.agent.graph import MAX_TOOL_ROUNDS, ask
from evals.fixtures import fixture_context


class ScriptedLLM:
    """Answers from a script; records the messages it was given."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.tool_calls_offered = []
        self.bound = False

    def bind_tools(self, tools):
        bound = ScriptedLLM.__new__(ScriptedLLM)
        bound.__dict__ = self.__dict__.copy()
        bound.bound = True
        bound.schemas = tools
        return bound

    async def ainvoke(self, messages):
        self.calls.append(list(messages))
        self.tool_calls_offered.append(self.bound)
        return self.responses.pop(0)


def _call(name, args, id_="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": id_}])


def _pricing_call():
    return _call("compare_pricing", {"competitors": ["Brightdesk"]})


async def test_answer_cites_numbered_tool_evidence():
    llm = ScriptedLLM(_pricing_call(), AIMessage(content="Pro is $39/month [1]."))
    result = await ask("What does Brightdesk charge?", fixture_context(), llm)

    assert result.answer == "Pro is $39/month [1]."
    assert result.citations_valid is True
    assert result.tool_calls[0].name == "compare_pricing"
    assert [s.cited for s in result.sources][0] is True
    assert any(not s.cited for s in result.sources)  # price changes are other sources
    assert '"source":1' in llm.calls[1][-1].content


async def test_the_same_evidence_keeps_its_number_across_calls():
    llm = ScriptedLLM(
        _call("compare_pricing", {"competitors": ["Nimbus"]}, "a"),
        _call("compare_pricing", {"competitors": ["Nimbus"]}, "b"),
        AIMessage(content="Starter rose to $25/month [1]."),
    )
    result = await ask("Nimbus?", fixture_context(), llm)
    assert len({s.number for s in result.sources}) == len(result.sources)
    assert len(result.sources) == 3  # two prices and one change, not six


async def test_made_up_citation_gets_one_retry_and_is_fixed():
    llm = ScriptedLLM(
        _pricing_call(),
        AIMessage(content="Pro is $39/month [99]."),
        AIMessage(content="Pro is $39/month [1]."),
    )
    result = await ask("q", fixture_context(), llm)
    assert result.answer == "Pro is $39/month [1]."
    assert result.citations_valid is True
    assert "[99]" in llm.calls[2][-1].content


async def test_citation_still_wrong_after_retry_is_removed_and_flagged():
    llm = ScriptedLLM(
        _pricing_call(),
        AIMessage(content="Pro is $39/month [99]."),
        AIMessage(content="Pro is $39/month [99]."),
    )
    result = await ask("q", fixture_context(), llm)
    assert result.answer == "Pro is $39/month ."
    assert result.citations_valid is False
    assert not any(s.cited for s in result.sources)


async def test_uncited_number_triggers_a_retry():
    llm = ScriptedLLM(
        _pricing_call(),
        AIMessage(content="Pro costs $39/month."),
        AIMessage(content="Pro costs $39/month [1]."),
    )
    result = await ask("q", fixture_context(), llm)
    assert result.citations_valid is True
    assert len(llm.calls) == 3


async def test_saying_there_is_no_data_needs_no_citation():
    llm = ScriptedLLM(AIMessage(content="The monitored pages don't cover that."))
    result = await ask("Who founded Nimbus?", fixture_context(), llm)
    assert result.citations_valid is True
    assert result.sources == []


async def test_citation_without_any_tool_call_is_invalid():
    llm = ScriptedLLM(
        AIMessage(content="Prices fell [1]."), AIMessage(content="I don't know.")
    )
    result = await ask("q", fixture_context(), llm)
    assert result.answer == "I don't know."
    assert result.citations_valid is True


async def test_bad_tool_arguments_go_back_to_the_model():
    llm = ScriptedLLM(
        _call("get_page_history", {"competitor": "Acme"}),
        AIMessage(content="There is no competitor called Acme."),
    )
    result = await ask("Acme?", fixture_context(), llm)
    assert "Unknown competitor" in result.tool_calls[0].error
    assert llm.calls[1][-1].status == "error"
    assert "Brightdesk" in llm.calls[1][-1].content


async def test_workspace_argument_from_the_model_is_rejected():
    llm = ScriptedLLM(
        _call("compare_pricing", {"workspace_id": "another-tenant"}),
        AIMessage(content="I can't do that."),
    )
    result = await ask("q", fixture_context(), llm)
    assert "workspace_id" in result.tool_calls[0].error
    assert result.sources == []


async def test_endless_tool_use_is_cut_off():
    calls = [_call("compare_pricing", {}, f"c{i}") for i in range(MAX_TOOL_ROUNDS)]
    llm = ScriptedLLM(*calls, AIMessage(content="Enough."))
    result = await ask("q", fixture_context(), llm)
    assert result.answer == "Enough."
    assert len(result.tool_calls) == MAX_TOOL_ROUNDS
    assert llm.tool_calls_offered[-1] is False


async def test_token_usage_is_summed_across_calls():
    first = _pricing_call()
    first.usage_metadata = {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12}
    second = AIMessage(content="None of that is on the pages.")
    second.usage_metadata = {"input_tokens": 30, "output_tokens": 5, "total_tokens": 35}
    result = await ask("q", fixture_context(), ScriptedLLM(first, second))
    assert (result.usage.input_tokens, result.usage.output_tokens) == (40, 7)


async def test_invented_price_without_any_tool_call_is_flagged():
    llm = ScriptedLLM(
        AIMessage(content="Acme charges $50/month."),
        AIMessage(content="Acme charges $50/month."),
    )
    result = await ask("q", fixture_context(), llm)
    assert result.citations_valid is False

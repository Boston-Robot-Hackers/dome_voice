# I03 The LLM gives up on repeated reply intents (get_status) and apologises instead

**Opened:** 2026-11-22 (found through dome_pad's Status key)

## Symptom

The same question, "What's your status?", was sent on `/voice/llm_text` several
times in one `llm_node` conversation (from dome_pad's Status key, one press
each). The first press worked: Claude called `get_status`, the reply was
empty, and dome_control's `motion_behavior` said "linear speed 0.2, angular
speed 0.7". After a few more, Claude stopped calling the tool and spoke
instead. From the VM's `llm_node` log:

```
Reply (LLM 1.5 s): "The status request keeps going out, but I still can't get a
reply from the robot. It may be worth checking the robot directly or restarting
its status service.", intents []
Text in: "What's your status?"
Reply (LLM 1.0 s): "I still can't get a status reply from the robot, so I'd
suggest checking it in person. I'll stop resending the request for now.", intents []
```

## What's known

- **Claude never sees the answer to a reply intent.** For `describe_scene`,
  `list_objects` and `get_status`, `RULES` tells it to say nothing because
  the robot speaks the answer itself. The only feedback it gets is
  `TOOL_RESULT_TEXT = "Sent to the robot."` (`llm_turn.py`), sent at the
  start of the next user message. So from Claude's side, each call looks
  unanswered.
- The robot side was fine: one `/intent`, one `/announcement` per call, seen
  live through rosbridge on 2026-11-22.
- dome_pad worked around it by sending `get_status` straight to `/intent`
  (dome_pad `f8659f4`). **Voice users asking for status repeatedly would hit
  the same thing.**

## Theories and fixes, most likely first

1. **Make the tool result say the answer is spoken elsewhere**, e.g. "Sent.
   The robot says the answer aloud itself; you will not see it. This is
   expected." Cheap; probably enough.
2. **Feed the spoken answer back**: `llm_node` subscribes to `/announcement`
   and passes the next reply-intent announcement into the conversation as
   the tool result. Accurate, but the answer arrives after the turn ends,
   so it needs the held-result mechanism to carry it.
3. **Trim repeated identical turns** from the history.

## Next test

With fix 1, send "What's your status?" on `/voice/llm_text` ten times in a
row (`ros2 topic pub --once` in a loop) and check that every turn publishes
`get_status`.

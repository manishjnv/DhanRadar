# Screen — AI Assistant

**Purpose.** Grounded multi-turn chat; answers carry actions, confidence, cited sources, feedback.

## Layout
Chat transcript (user right, AI left). AI bubbles carry sources/confidence/feedback. Sticky composer (SSE stream) + suggested prompts.

## Components
- ChatTranscript
- MessageBubble
- Composer(SSE)
- SuggestedPrompts

## API requirements
- `POST /v1/ai/assistant (SSE)`
- `POST /v1/ai/messages/{id}/feedback`

## Data model (entities)
- ai_conversations
- ai_messages

## Loading states
Typing indicator (animated dots) while streaming.

## Error states
Model unavailable → error bubble + retry; never fabricates; "not advice" persists.

## Responsive rules
Full-height column; composer pinned; mobile keyboard-aware.

## Analytics events
- `assistant_open`
- `assistant_ask`
- `assistant_feedback`
- `assistant_drill`

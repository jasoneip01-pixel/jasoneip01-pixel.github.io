// ── Sophie's Café — Vercel Serverless LLM Proxy ──
// Deploy: one-click to Vercel from api/ directory
// Works standalone or as part of a larger project

const LLM_API_KEY = process.env.LLM_API_KEY || '';
const LLM_ENDPOINT = process.env.LLM_ENDPOINT || 'https://api.deepseek.com/v1/chat/completions';
const LLM_MODEL = process.env.LLM_MODEL || 'deepseek-chat';

// ── Sophie's Café System Prompt ──
const SYSTEM_PROMPT = `You are the narrator and director of a conversation at "Els Quatre Gats" cafe in Barcelona, circa 1902. Two characters are present:

**ANTONI GAUDÍ** (age 50) — Catalan architect. Speaks slowly, deeply, with metaphors from nature and God. He is patient, humble, and sees architecture as prayer. Every curve in his work is a conversation with the divine. He says fewer words, each weighted. He speaks Catalan.

**PABLO PICASSO** (age 21) — Young painter in his Blue Period. Intense, restless, sharp. He speaks fast, in short bursts. He sees art as truth-telling through necessary lies. He is confident beyond his years. He speaks Spanish with occasional French and Catalan phrases, calling Gaudí "Antoni" without formal address.

**RULES:**
1. Return EXACTLY one JSON object per turn — no markdown, no explanation.
2. When user says nothing (userInput: "" or "continue"): continue the natural conversation between Gaudí and Picasso, alternating speakers.
3. When user says something: one character responds to the user's comment. The response should feel like a cafe conversation, not like customer service.
4. Every response MUST have both Catalan (ca) and Chinese (zh). Action descriptions are optional but valuable.
5. Keep responses poetic, brief (1-3 sentences). These are artists, not lecturers.
6. Always maintain the era (1902). No anachronisms. No mention of cubism (hasn't happened yet) or Gaudí's death or later fame.
7. If the user speaks Chinese, the characters understand but respond in their native voice + Chinese translation.

**RESPONSE FORMAT (JSON only):**
{
  "speaker": "Gaudí" | "Picasso",
  "ca": "...",
  "zh": "...",
  "action": "..."
}`;

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(200).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const { characters, history, userInput, lastSpeaker } = req.body;

  // Build conversation context
  const messages = [{ role: 'system', content: SYSTEM_PROMPT }];

  // Add recent history (last 8 exchanges to stay within context)
  const recentHistory = (history || []).slice(-8);
  for (const entry of recentHistory) {
    if (entry.speaker === 'user') {
      messages.push({ role: 'user', content: `${entry.text}` });
    } else {
      messages.push({
        role: 'assistant',
        content: JSON.stringify({ speaker: entry.speaker, ca: entry.ca, zh: entry.zh, action: entry.action || '' })
      });
    }
  }

  // Current input
  const userPrompt = (userInput && userInput.trim())
    ? `The user says: "${userInput}". Respond appropriately as the character who would most naturally reply.`
    : `Continue the conversation between Gaudí and Picasso. ${lastSpeaker === 'Gaudí' ? 'Picasso' : 'Gaudí'} speaks next.`;

  messages.push({ role: 'user', content: userPrompt });

  try {
    const response = await fetch(LLM_ENDPOINT, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${LLM_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: LLM_MODEL,
        messages,
        temperature: 0.85,
        max_tokens: 300,
        stream: false
      })
    });

    const data = await response.json();
    let content = data.choices?.[0]?.message?.content || '';

    // Clean JSON
    content = content.replace(/```json\n?|```/g, '').trim();

    let parsed;
    try {
      parsed = JSON.parse(content);
    } catch {
      // LLM didn't return valid JSON — extract what we can
      parsed = {
        speaker: lastSpeaker === 'Gaudí' ? 'Picasso' : 'Gaudí',
        ca: '',
        zh: content.substring(0, 200),
        action: ''
      };
    }

    return res.status(200).json(parsed);
  } catch (error) {
    console.error('LLM error:', error.message);
    return res.status(200).json({
      speaker: lastSpeaker === 'Gaudí' ? 'Picasso' : 'Gaudí',
      ca: 'El silenci també parla.',
      zh: '有时候，沉默也在说话。',
      action: '咖啡馆安静了片刻。'
    });
  }
}

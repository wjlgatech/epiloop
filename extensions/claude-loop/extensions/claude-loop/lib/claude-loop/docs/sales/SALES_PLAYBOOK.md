# Claude-Loop Sales Playbook
## For AI Startups Building Autonomous Agents

**Target:** Technical founders and engineering leads at AI startups
**Price Point:** $5K-15K/month (starting)
**Sales Cycle:** 2-4 weeks

---

## 60-Second Elevator Pitch

> "You know how every AI startup is trying to build autonomous agents, but they all hit the same wall—context limits, no memory between sessions, and agents that keep making the same mistakes?
>
> We built claude-loop, an infrastructure layer that solves this. It breaks complex tasks into story-sized chunks, persists memory through files, and—here's the key part—it learns from every failure automatically. 95% classification accuracy on why things fail, with human-gated improvement so you stay in control.
>
> Our system improved itself using its own features. Literally. We pointed it at its own codebase and said 'build a monitoring dashboard.' Forty minutes later, done.
>
> If you're building agents, this is the infrastructure you're going to build anyway—or you can license ours and ship 6 months faster."

---

## The "Self-Healing Agent" Demo Script (5 minutes)

### Setup (30 seconds)
"Let me show you something that will change how you think about autonomous agents."

```bash
cd demo-project
# Show a deliberately ambiguous PRD
cat prd-ambiguous.json
```

**What to show:** A PRD with intentionally vague acceptance criteria like "make the API fast" or "improve user experience."

### Failure Phase (1 minute)
"Watch what happens when we give the system an ambiguous requirement."

```bash
./claude-loop.sh --prd prd-ambiguous.json --max-iterations 3
```

**What happens:**
- System attempts implementation
- Quality gates fail (tests don't pass because requirements are unclear)
- Iteration 2 tries again, fails again
- System recognizes the pattern

### Classification Phase (1 minute)
"Now here's the magic. The system just classified WHY it failed."

```bash
cat .claude-loop/logs/failure-classification.json | jq .
```

**Show:**
```json
{
  "failure_type": "boundary_error",
  "subtype": "ambiguous_requirements",
  "confidence": 0.92,
  "root_cause": "Acceptance criteria 'make API fast' lacks measurable threshold",
  "suggested_fix": "Clarify: define latency target in ms (e.g., <200ms p95)"
}
```

### Improvement Generation (1 minute)
"And now it generates an improvement proposal."

```bash
cat .claude-loop/improvement-queue/proposal-001.json | jq .
```

**Show:**
```json
{
  "improvement_id": "IMP-001",
  "problem_pattern": "Ambiguous performance requirements",
  "proposed_solution": "Add PRD validation rule requiring quantitative metrics",
  "test_cases": ["fast", "quick", "efficient", "improve"],
  "status": "pending_human_review"
}
```

### The Kicker (1 minute)
"This proposal goes into a human-gated queue. When I approve it, the system literally gets smarter. Next time someone says 'make it fast,' the system will ask 'what's your latency target?'

**That's the meta-reasoning loop your competitors don't have.**

The experience store tracks every problem-solution pair by domain—web, mobile, ML, whatever. Each failure makes the system better. And because it's human-gated, you never lose control."

### Close (30 seconds)
"This is what you'd have to build anyway. We've got 55,000 lines of production code, 15 self-improvement modules, and 95% accuracy on failure classification. You can build this from scratch, or you can license it and ship your product 6 months faster. What questions do you have?"

---

## Customer Discovery Questions

### Opening (warm up)
1. "What are you building?" (Let them talk, take notes)
2. "How are you handling [autonomous loops / memory / context limits] today?"
3. "What's the most frustrating limitation you hit regularly?"

### Pain Discovery
4. "When your agent fails, how do you figure out why?"
5. "How do you prevent it from making the same mistake twice?"
6. "How much time does your team spend on agent debugging vs. feature development?"
7. "What happens when you need to scale to 10x more users? 100x?"

### Value Discovery
8. "If your agent could learn from every failure automatically, what would that mean for your roadmap?"
9. "What would you pay for infrastructure that cuts your agent development time in half?"
10. "Who else needs to be involved in this decision?"

### Closing
11. "I'd like to offer you a 2-week pilot. You bring a real use case, we help you implement it with claude-loop, and we measure the results. If it works, we talk pricing. If not, you've learned something. Sound fair?"

---

## Objection Handling

### "We can build this ourselves"
"Absolutely you can. The question is, should you? We've invested 18 months and 55,000 lines of code into this. That's 6-9 months of your senior engineer's time. If your core IP is the agent infrastructure itself, build it. If your core IP is what the agent does, license the infrastructure and focus on your differentiation."

### "It's too expensive"
"What's your current cost per failed agent run? How many hours does debugging take? If this saves one senior engineer 20% of their time, that's $30K/year in salary alone. The ROI math usually works out to 3-5x within the first quarter."

### "We're not ready yet"
"That's exactly when infrastructure decisions matter most. The patterns you establish now will either scale or become technical debt. Let's do a small pilot—2 weeks, one use case—and you'll know if this is right for you."

### "We use a different LLM / framework"
"Claude-loop is LLM-agnostic. We support Claude, GPT-4o, Gemini, and DeepSeek out of the box. The value isn't the model—it's the memory layer, the quality gates, and the self-improvement loop."

### "Open source? Why pay?"
"The core is open source. You're paying for support, custom domain adapters, priority features, and enterprise integrations. Most companies find that the support alone pays for itself in the first month."

---

## Pricing Framework

### Tier 1: Starter ($5K/month)
- Full claude-loop license
- 3 domain adapters
- Email support (48h response)
- Community Slack access

### Tier 2: Growth ($10K/month)
- Everything in Starter
- Custom domain adapter development (1/month)
- Priority support (4h response)
- Quarterly roadmap input

### Tier 3: Enterprise ($25K+/month)
- Everything in Growth
- Dedicated success manager
- Custom agent development
- On-prem deployment option
- SLA with uptime guarantees

### Pilot Program (Free)
- 2-week trial
- One use case
- Engineering support
- Success = convert to paid

---

## Target Company Profile

### Ideal Customer
- **Stage:** Seed to Series B
- **Team:** 5-50 engineers
- **Building:** Autonomous agents, AI assistants, coding tools
- **Pain:** Context limits, debugging time, scaling concerns
- **Budget:** $50K-500K annual AI infrastructure spend
- **Timeline:** Shipping product within 6 months

### Red Flags
- No clear product vision (exploring vs. building)
- Infrastructure is their core IP (competing)
- Budget under $30K/year (not ready)
- No technical decision maker available

### Where to Find Them
- AI/ML meetups (your current plan ✓)
- Y Combinator / Techstars batches
- Twitter/X AI builder communities
- Discord servers (Latent Space, MLOps Community)
- Product Hunt launches in AI category

---

## Follow-Up Templates

### After Initial Meeting
```
Subject: Following up: claude-loop for [Company Name]

Hi [Name],

Great talking today about [specific thing they're building].

Based on what you shared about [their pain point], I think claude-loop could help you [specific benefit].

Next step: Let's schedule a 30-minute technical deep-dive where I can show you the self-improvement loop in action. [Calendar link]

Best,
Wu
```

### After Demo
```
Subject: Ready to start your pilot?

Hi [Name],

Thanks for taking the time to see the demo. I noticed you were particularly interested in [specific feature they reacted to].

As discussed, I'd like to offer you a 2-week pilot:
- You bring a real use case
- We help you implement it
- We measure results together

No charge, no commitment. If it works, we talk pricing. If not, you've learned something valuable.

Ready to get started? [Calendar link]

Best,
Wu
```

### After Pilot Success
```
Subject: Pilot results + next steps

Hi [Name],

Congrats on completing the pilot! Here's what we achieved:
- [Metric 1: e.g., "40% reduction in debugging time"]
- [Metric 2: e.g., "3 features shipped vs. planned 1"]
- [Metric 3: e.g., "Zero context-limit failures"]

Based on your usage patterns, I recommend starting with our [Tier] plan at $[X]/month.

Next step: 30-minute call to finalize terms and kick off onboarding. [Calendar link]

Best,
Wu
```

---

## Success Metrics to Track

### Pipeline Metrics
- Conversations per week: Target 10
- Demos per week: Target 5
- Pilots per month: Target 4
- Conversion rate (demo → pilot): Target 50%
- Conversion rate (pilot → paid): Target 60%

### Revenue Metrics
- MRR: Track weekly
- Average contract value: Target $8K/month
- Time to first revenue: Target <90 days
- Churn rate: Target <5%/month

### Customer Metrics
- NPS score: Target 50+
- Support tickets per customer: Track trends
- Feature requests captured: Track themes

---

## Your Unfair Advantages (Use These!)

1. **Cross-cultural (US-CN)**: You can bridge AI ecosystems others can't. China's manufacturing + US capital = unique positioning.

2. **Builder credibility**: You built the product yourself. 55K lines of code. You understand the pain deeply.

3. **Faith-driven resilience**: You'll outlast competitors in the trough of sorrow. Play the long game.

4. **First principles**: You think clearly about hard problems. Customers sense this.

5. **Action bias**: You move fast. Speed is a feature.

---

*Last updated: January 2026*
*Author: Wu + Claude*

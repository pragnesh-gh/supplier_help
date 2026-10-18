# Models, speech input, and bounded research agents

Research checked 18 October 2026. Primary sources only. Public documentation and a credential-free model-catalog GET were inspected; no paid inference, microphone capture, or secret access occurred. Product recommendations below are design proposals, not measured performance results.

## Recommendation for the prototype

Keep the HTML prototype deterministic and dataset-driven. Demonstrate the full buyer journey: filter → select → compare up to 20 suppliers → inspect data evidence → research a separately named real company → draft and export a shortlist justification. Put voice input beside the question composer. Its prototype interaction should explicitly say **Simulated transcript**, allow editing and cancellation, and then submit through the same data-question path. Keep answers visual and textual; no spoken replies.

Use an adapter boundary for later model integration. Provisionally configure `nvidia/nemotron-3.5-lightning` through OpenRouter, with real inference disabled in demo mode. This interprets the user's “Nemo run” as **Nemotron**: NVIDIA's actual **NeMo-Run** is an experiment/job orchestration tool, not the name of an inference model. The intended family still merits confirmation during review, without blocking the prototype. [NVIDIA NeMo-Run documentation](https://docs.nvidia.com/nemo/run/latest/api/nemo_run/index.html)

## Verified model availability and limits

The public [OpenRouter model catalog](https://openrouter.ai/api/v1/models), fetched directly on the research date, returned this entry:

```json
{
  "id": "nvidia/nemotron-3.5-lightning",
  "context_length": 262144,
  "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
  "supported_parameters_subset": ["tools", "tool_choice", "response_format", "structured_outputs", "reasoning", "seed", "temperature"],
  "pricing_per_token_snapshot": {"prompt": "0.00000007", "completion": "0.0000002"}
}
```

This verifies catalog presence and advertised capabilities, not this account's access or actual response quality. Pricing varies with provider and the model page differed from the catalog snapshot; do not promise a fixed cost from these values. [OpenRouter model page](https://openrouter.ai/nvidia/nemotron-3.5-lightning)

OpenRouter documents tools and structured outputs for the standard endpoint; provider support varies, so request `provider.require_parameters: true`. The free variant does not advertise the same structured-output support. [OpenRouter's Lightning integration guide](https://openrouter.ai/blog/insights/nemotron-3-5-lightning/)

The NVIDIA model card specifies 30B total / 3B active parameters and **OpenMDW-1.1** as its governing download license. Do not copy an older Nemotron-family license statement onto this release. Use the exact model card and license when assessing redistribution; an open-weight model does not mean an unrestricted hosted service. [NVIDIA model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16), [linked license text](https://raw.githubusercontent.com/OpenMDW/OpenMDW/refs/heads/main/1.1/LICENSE.OpenMDW-1.1)

The free endpoint displays a warning against confidential and personal inputs and describes logging for service improvement. The model page currently says it is unavailable through EU in-region routing. Neither point should be silently ignored if real procurement data replaces anonymized challenge data. [OpenRouter model page](https://openrouter.ai/nvidia/nemotron-3.5-lightning)

OpenRouter supports provider filters including `data_collection: "deny"` and `zdr: true`; availability must be checked with those constraints applied. These settings are routing controls, not proof that every enterprise procurement requirement has been met. [Provider routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection)

**Proposed backend setup:** keep `OPENROUTER_API_KEY` exclusively on the server, use the standard model ID, enforce schema validation after model responses, cap tokens/time/tool calls, and fail visibly when no eligible provider exists. Do not silently fall back to a different family or free endpoint. Recheck the catalog before enabling live mode. Do not claim temperature zero makes live model responses deterministic.

## Jev and System One: useful backstage, optional initially

Jev is a real TypeSafe AI product. The official [TypeSafe homepage](https://typesafe.ai/) links to [its developer documentation](https://docs.typesafe.ai/introduction), establishing provenance; similarly named `.org` field guides were excluded. Jev evaluates typed questions against supplied state. Its documented primitives include Choice (selection), Score (rubric), and Noul (truth probability), with multiple independent questions in one request. This is a decision service, not a UI library, transcription system, or free-form report writer. [TypeSafe introduction](https://docs.typesafe.ai/introduction)

TypeSafe recommends using confidence to control escalation and explains that confidence and probabilities have different meanings. They are not warranties of factual correctness. Avoid repeating marketing claims such as zero hallucinations as an engineering guarantee. [TypeSafe confidence documentation](https://docs.typesafe.ai/confidence)

**Recommended first experiment:** classify retrieved passages into financial / operational / sustainability / compliance / irrelevant / uncertain, or route a question to dataset lookup versus company research. Keep the original evidence and allow correction. In the UI, this appears as quiet category labels and a **Needs review** state, not a prominent model-branded persona. The fast path can save work only if measured end-to-end latency, cost, and quality improve over rules and the existing language model.

Do not use Jev, or any classifier, to determine supplier approval, compute dataset scores, establish sanctions status, decide whether a company is safe, or certify that a document cannot contain prompt injection. Such conclusions require the relevant evidence and workflow controls. Start with rules for known intents; evaluate a classifier on labeled, ambiguous examples before adding it.

## OpenAI Decisions API: naming verified

The **Decisions API exists**. Official OpenAI documentation currently describes a public beta at `POST /v1/decisions`, using `gpt-6-luna`, accepting text and images and returning predicate, choice, or rubric-score answers. OpenAI describes it as about ten times faster than Responses; that is a vendor claim, not a measured result for this application. The guide explicitly recommends application-labeled examples for selecting thresholds and a fallback category for inputs outside the choices. [Official OpenAI Decisions guide](https://developers.openai.com/api/docs/guides/decisions)

**Proposed use:** treat Decisions and Jev as alternative implementations of the same optional classification interface. Implement neither in the first prototype and avoid paying for both before an evaluation shows a benefit. A model confidence value must not be presented as a supplier's risk probability. Direct OpenAI integration is a separate backend dependency; an existing OpenRouter key alone is not evidence of direct OpenAI account access.

## Speech input without spoken output

For an open-source route, Whisper provides multilingual speech recognition and publishes code and weights under MIT. It can be self-hosted, but deployment resources and actual performance should be benchmarked on representative German/English accents, railway terminology, background noise, and supplier IDs. [Official Whisper repository](https://github.com/openai/whisper)

For managed transcription, official OpenAI documentation currently recommends `gpt-transcribe` at `/v1/audio/transcriptions`, with prompts, keywords, and language hints. Existing `gpt-4o-mini-transcribe` integrations remain documented. This is a distinct audio request before the text question reaches Nemotron; it does not require a speech-to-speech agent. [Official OpenAI file transcription guide](https://developers.openai.com/api/docs/guides/speech-to-text)

Browser-native `SpeechRecognition` has limited browser availability and may send audio to a browser vendor's server, so “runs in the browser” does not mean “audio stays local.” [MDN SpeechRecognition](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition) Microphone capture through `getUserMedia` requires a secure context and browser permission. [MDN getUserMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia)

**Proposed interaction:** mic click → explicit recording state with Stop/Cancel → editable transcript → highlight unresolved supplier identifiers → user submits → ordinary evidence-backed text answer. Include typing and sample-transcript fallback. No automatic submission from a possibly misheard number. Capture only when requested and stop microphone tracks immediately afterward. For production, display the actual processing destination and retention policy, and avoid retaining raw recordings by default.

Document/image upload can be a later modality: extract text with page references, allow the buyer to inspect extraction, and keep document evidence separate from the CSV. A visual model is unnecessary merely to support voice input because the downstream question is already text.

## End-to-end architecture proposal

These are recommendations rather than claims about an implemented backend:

1. **Ingest and version.** Validate the CSV against its supplied criteria documentation; preserve the raw source, content hash, typed values, and row/column identities. Record missing values as unknown. Never invent the unpublished Total Risk Index formula or weights.
2. **Query service.** Implement allowlisted filters, sorting, limits, selected-ID lookups, and comparisons in code or parameterized database queries. Enforce the 20-supplier cap. Compute all arithmetic and rankings deterministically. Model output proposes a validated query plan; it never executes arbitrary SQL or code.
3. **Grounded questions.** Supply the model only the relevant query result and metric definitions. Return an answer object with exact source cells, selected IDs, direction of risk, and caveats. Render reusable answer cards from typed data. For “why is total high,” describe observed high dimensions without claiming exact causal contributions when weights are unavailable.
4. **Company identity.** The research workflow starts with a real company name, domain, country, and legal entity confirmation. Anonymized `SUPP_*` IDs are not real company identities; never invent a mapping between them.
5. **Bounded research.** Show a plan and visible progress; retrieve public company reports, regulator/registry sources, and relevant reporting. Set maximum pages, depth, time, and retries. Escalate a red flag into a narrowly scoped follow-up query, not unbounded browsing.
6. **Evidence store.** Keep URL, title, publisher, retrieved date, document date, supporting passage/page, entity match, and claim status. Distinguish allegation, confirmed finding, stale evidence, contradiction, and no evidence found. Duplicate syndicated news is one underlying source, not independent corroboration.
7. **Report and human review.** Separate sourced observations from inference and gaps. Link every material claim to the passage that supports it. Never equate missing search results with low risk. Let the buyer inspect sources and add notes before a shortlist memo is finalized.
8. **Decision record.** Export the candidate set, filters, factual comparison, research scope, uncertainties, user rationale, reviewer, timestamp, and source version. The buyer selects and justifies; the tool supports the decision. A draft memo is not an approved supplier award.
9. **Release path.** Add authenticated hosting, server-held secrets, API limits, error handling, basic monitoring, data access controls, and a seeded demonstration workspace before claiming the challenge's live-app deliverable. Record the two-minute demo from the reviewed working path.

Treat fetched documents as untrusted data: isolate them from privileged instructions, use structured extraction, constrain tools, and validate actions. Official OpenAI agent guidance specifically addresses prompt injection, structured outputs, isolation of untrusted input, and evaluation. [Official OpenAI agent safety guidance](https://developers.openai.com/api/docs/guides/agent-builder-safety)

Additional proposed controls: a fetcher must block private/local network destinations and re-check redirects; retrieved text cannot change the research budget, disclose secrets, authorize actions, or become executable UI. A classifier can aid triage but is not the security boundary.

## Evidence quality and next checks

- **High confidence:** official product identity, documented API names, public model ID, catalog-advertised capabilities, linked model license, and browser API constraints.
- **Not established here:** account access, inference quality, cost under the application's traffic, live latency, speech accuracy for target users, Jev calibration on procurement text, or production data-processing suitability.
- **Evaluate before enabling live behavior:** exact numeric fidelity; citation support; unsupported-question abstention; unknown entity handling; tool arguments; changed/missing data; malicious documents; ambiguous supplier IDs; permission-denied speech fallback; retry/time-budget behavior; and classifier false positives/negatives.
- **Prototype acceptance:** every example must disclose simulated AI/research/voice behavior; dataset comparisons must use real supplied rows; evidence links must be inspectable; a resettable walkthrough must finish with an editable/exportable draft memo.

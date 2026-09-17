# Citations are checked deterministically; the request path has no LLM-as-judge

Every Citation must match a retrieved Article (article identity or quoted text). If no valid Citation remains, the answer is Insufficient Evidence. An LLM judge on the request path was rejected: acceptance tests are PDF-checkable facts, and a judge model can agree with a fabricated Citation.

**Status:** accepted

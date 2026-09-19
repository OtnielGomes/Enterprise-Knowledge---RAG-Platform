# PGD Teletrabalho

The v1 bounded context: a Unifesp technical-administrative servant asks about currently effective telework rules and receives a cited answer from a dated snapshot of numbered normative acts — or an explicit refusal.

## Programme

**PGD**:
Programa de Gestão e Desempenho — the federal and institutional programme under which telework may be authorized. It is not a right of the Servidor.
_Avoid_: Home-office policy, remote-work program, HR policy, knowledge base

**Teletrabalho**:
Remote work under PGD rules; the subject of v1 questions.
_Avoid_: Home office, remote work, hybrid (as the name of this domain)

## People

**Servidor**:
A Unifesp technical-administrative education staff member (TAE) who is subject to the institution's PGD telework rules and is the primary person the assistant serves.
_Avoid_: User, employee, colaborador, customer, end user

**Chefia**:
The Servidor's immediate manager. Not a primary user; appears only as extra golden-set questions, with no approval workflow.
_Avoid_: Gestor, manager, approver, admin

## Normative acts

**Normative Act**:
A numbered legal instrument in the snapshot (a Unifesp Resolução, a federal Decreto, or an Instrução Normativa).
_Avoid_: Policy, PDF, file, document, knowledge article, source file

**Article**:
A numbered article inside a Normative Act, including its caput, paragraphs, and items; the unit of knowledge the assistant cites.
_Avoid_: Chunk, passage, paragraph, section, snippet

**Current**:
A Normative Act that is in force for default answers.
_Avoid_: Latest, new, live, vigente (in code and English docs; the UI may say vigente)

**Superseded**:
A Normative Act revoked or replaced by a later act (the Unifesp Resolução 213/2021 relative to 262/2025). Retrieved only for a Historical Question.
_Avoid_: Archived, expired, old, deleted, draft, previous version (it is not a version of the later act)

**Supersession**:
The relationship in which one Normative Act revokes and replaces another. The two acts keep distinct identities (different numbers); they are not versions of a single act.
_Avoid_: Version, revision, update, file version

**Amendment**:
A Normative Act that changes parts of another without replacing it (IN 21/2024 relative to IN 24/2023). Both remain Current. The assistant does not merge them into a consolidated text.
_Avoid_: Replacement, Supersession, consolidated version, patch of the same act

**Historical Question**:
A question that asks for a past, revoked, or pre-262 rule. This is the only case in which a Superseded act may be retrieved.
_Avoid_: Old query, archive search, version query

**Corpus Cutoff**:
The calendar date of the snapshot the assistant is allowed to know. Answers are true as of that date, not as of today's official gazette.
_Avoid_: Live knowledge, latest law, index time, today

## Answering

**Citation**:
A pointer to a specific Article in a Normative Act (act identity, act number, page) that supports a claim in the answer and that a human can open and check.
_Avoid_: Source, reference, link, chunk id (as the user-facing concept)

**Insufficient Evidence**:
The single refusal state in v1: retrieved Articles cannot support an answer, or the question is outside the PGD telework snapshot. The assistant refuses rather than guessing. Eval may distinguish “out of slice” from “retrieve missed”; the Servidor sees one refusal.
_Avoid_: Hallucination, no results, error, I don't know, empty retrieval, out of scope (as a user-facing state)

**Golden Set**:
A Portuguese collection of questions whose expected Normative Act, expected Article, and `must_abstain` are owned by a human annotator — the accepted measure of whether Ask is right.
_Avoid_: RAGAS, traces, LLM-as-judge gabarito, eval dataset (as the source of truth)

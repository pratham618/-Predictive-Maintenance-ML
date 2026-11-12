# Minimal dark workspace

The frontend now prioritizes operating decisions: latest machine conditions,
items needing attention and open maintenance. The model, threshold, persistence
and maintenance/outcome rules are unchanged.

## Navigation

- Operations: Overview, Run prediction, Machines & history, Maintenance.
- Model & data: Model performance, Datasets.
- Preferences: Settings, including the existing light-appearance option.

New assessment is a prominent sidebar action. Search (Ctrl/Cmd+K), assessment
shortcut (Ctrl/Cmd+Shift+P), machine alerts and every existing route remain
available. Page URLs and saved records do not change.

## Overview

The first four cards show assigned machines, latest high-risk machines, machines
needing attention and Open/In progress work. Operating cards exclude samples,
reference rows and unassigned snapshots. Repeated high-risk readings count once
per machine using the latest assessment; completed/cancelled work is not open.
Attention includes watch, rising-risk and stale-assessment rules.

The machine table includes latest probabilities, risk labels, times and alerts.
Open work has its own follow-up list. Risk trends compare one machine and its
latest saved model/threshold, rather than connecting unrelated machines.
Recent assessments include labeled samples so users can still find their tests.
Model metadata and measured latency are in expandable details; validation remains
on Model performance.

The workspace opens with saved data, not a demonstration. An optional reference
demo is isolated below the operational sections and never changes their counts.
All views continue to state that there is no live sensor connection. Empty
states explain the next action without claiming that unassessed machines are
healthy.

## Predictions and histories

The main prediction result emphasizes probability, textual risk and a suggested
next action. Source and assessment time stay visible. Samples remain labeled.
Run metadata is expandable. Explanation, original inputs, derived metrics and
downloads stay available under Explanation, inputs & downloads. Explanation
computation is deferred until that expander opens.

Reference-sample loading is secondary to the actual input form. Machine IDs,
sample declarations, validation, batch uploads and exports work as before.
Machines & history also shows maintenance work for the selected machine.

## Appearance

Charcoal backgrounds, restrained teal actions, neutral borders, system fonts
and readable labels replace the decorative model graphic, circular result gauge,
large brand block and entry animation. Native headings, material icons and
status badges improve semantic structure. Risk remains a written label as well
as a color. Focus outlines, reduced-motion behavior and responsive layouts are
preserved. System fonts remove the former Google Fonts request.

Launch from the repository root so Streamlit loads .streamlit/config.toml.
Restart Streamlit after pulling theme changes.

## Validation

Tests exercise every route, empty and populated overviews, latest-machine and
work counts, demo isolation, a real saved-model sample prediction, source labels,
and deferred explanation rendering. All prior workflow tests remain in the suite.
Tests use temporary databases and do not modify the user's history.

Browser visual review was unavailable in the authoring environment: the browser
could not reach the loopback preview and Windows browser control stopped because
the active URL could not be verified. Desktop/mobile pixel layout and keyboard
focus should still be reviewed in a real browser before merging.

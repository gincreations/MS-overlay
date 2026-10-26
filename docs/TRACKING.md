# Tracking behavior

## EXP and level ETA

Main EXP/hour = accumulated gross EXP gain / active tracked seconds × 3,600, available after the original ten seconds. The recent rate uses retained samples over approximately five active minutes, with a minimum sample span of 30 seconds. Level-up ETA uses a positive recent rate when available, otherwise the session average: remaining EXP / rate × 3,600.

The original no-EXP timeout defaults to 15 seconds. Idle pauses rewind counted time to the last EXP gain; manual Pause also excludes time. Walking or waiting can therefore produce a higher active-time rate than a stopwatch average. Confirmed death losses do not subtract from gross gained EXP. Main rate and ETA can differ because they do not always use the same averaging window.

The inherited private-capture limitation remains: manual Pause stops reading, and unseen EXP gains may be credited on Resume without including paused time. Map changes can start a new session. These are preserved calculation policies, not guarantees of real-hour earnings. No new 60-second EXP warm-up is used.

## Mesos

Mesos/hour = confirmed inventory balance change / active seconds since the first counting baseline × 3,600, after the original 30 active seconds. It shares the EXP session clock. The first balance needs three identical readings; constantly changing balances can delay initial confirmation. Purchases, sales and transfers can affect the total; suspicious large jumps are treated as new baselines rather than earnings. This is not a drop-only or net-profit ledger.

If the inventory moves, two failed old-position crops trigger an earlier search. A newly covered old location also triggers a search. Confirmation state for the old crop is cleared when a new location is found, without clearing learned fonts or tracker/session totals. Unsuccessful outline searches retain backoff. Recognition cannot read hidden, clipped or unreadable digits; multiple visible balance fields such as storage/trade are rejected when detected as ambiguous.

## Optional potions and costs

Select up to two supported item types. Both Off disables sampling and hides the readout. A verified classic 4×2 hotbar is checked first using bundled key-label, icon and digit references. Its displayed count represents total carried stock (owner-reported game behavior). Duplicate quickslots must agree and are read once, never summed. A readable zero is valid. When a selected item is absent or unreadable on the hotbar, the verified visible Use-tab inventory is the fallback: readable visible stacks are combined, with consecutive readings confirming changes. Hidden inventory stacks are not counted by the fallback.

Only one source is used per selected item. Opening the inventory cannot double count a readable hotbar. Changing source or visible slot layout resets the count baseline, not accumulated usage/cost or observed time. A gap is unavailable, never zero. Missing labels, unsupported layouts, occlusion, disagreement or ambiguous icons/counts cause a fallback or unavailable reading. The feature targets the shown classic 4×2 panel, not every custom/expanded hotbar layout. Refills and observation gaps establish new stock baselines without erasing confirmed usage. Selling or dropping items can resemble consumption; this is an estimate rather than a game-event log.

Usage/minute = confirmed estimated items used / observed seconds × 60, after 15 seconds of valid observations. Cost = items used × selected unit price. Potion spending/hour = usage/minute × 60 × unit price. It is separate from the main mesos/hour statistic and is not automatically deducted from it. Change prices to what you actually paid; NPC defaults are reference snapshots, not live shop quotes. Blank prices hide costs; zero explicitly means free.

There is no restock countdown. Stock/digit confidence rules remain conservative; missing readings are not treated as zero stock.

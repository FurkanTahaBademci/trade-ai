# Technical terminal interface — 2026-09-28

The web interface now uses a compact research-terminal layout across all routes.
The shared shell has grouped navigation, a narrower sidebar, keyboard focus
handling for the mobile menu, and a skip link. It removes the nonfunctional
notification button and decorative account/status indicators. Theme preference
and system-theme behavior remain unchanged.

## Presentation changes

- Shared light/dark tokens, flat panels, compact tables, tabular numeric text,
  rectangular controls, and visible keyboard focus.
- Shared `DataMetric` and numeric `ScoreMeter` replace duplicate metric cards
  and circular score displays across overview, instrument, analysis, portfolio,
  backtest, macro, institutional, and operations pages.
- Signals are a comparison table. News, KAP and analysis feeds use compact rows;
  cursor pagination, filters and loading/error handling retain their existing hooks.
- Markets initially show the searchable instrument list; the heatmap remains
  available through the view controls.
- Briefing evidence and raw analysis JSON are expandable. News/KAP links are
  separated from ticker links to avoid nested anchors.
- Overview collector status comes from each collector's health record. Impact
  strength is no longer shown as positive sentiment. Missing analysis confidence
  displays a dash.
- Mobile portfolio/table overflow and primary-button contrast were corrected.
  Chart palettes and controls follow the terminal theme.

## Verification

- `npm run lint`: passed.
- `npm test`: 42 tests passed.
- `npm run build`: passed; all application routes compiled.
- Static React rendering of 17 page templates, including four detail templates,
  in light/dark at 390, 768 and 1440 pixels: 102 browser checks, no page-level
  horizontal overflow. Wide data tables retain their own horizontal scroll.
- Browser interaction checks: mobile menu open/close, focus trap, Escape and
  focus restoration; theme toggle; ticker search; market view switching;
  command palette open/close; chart canvas rendering and candle/line switching.
  No uncaught browser exceptions in that interaction run.
- Screenshots inspected for overview, signals, news, markets, macro and system.

These checks used file-based previews and temporary tooling under
`/tmp/trade-terminal-preview` and `/tmp/trade-terminal-tools`; no local TradeAI
service was started. Feed/compare fixtures came from public production reads;
other preview data was illustrative. Static previews do not validate production
SSR/hydration, server actions, or external API availability. Those require the
post-deployment smoke check. Preview files and fixtures are not shipped.

Existing operational follow-ups (access control for system actions and old AI
failure/retry records) remain separate from this interface change.

/**
 * Pipeline Health wiring in the admin metrics dashboard controller.
 *
 * The card must request a window-wide floor (`partitionByBucket: false`, no
 * `resolution`) and hand the renderer the legend `<ul>`; a DOM lacking the
 * legend element skips the render the same way a missing `<svg>` does.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseriesSpy,
  renderPipelineHealthChartSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  fetchGaugesTimeseriesSpy: vi.fn(),
  renderPipelineHealthChartSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: vi.fn(),
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseries: fetchGaugesTimeseriesSpy,
}));

vi.mock("../render-summary.js", () => ({
  renderSummary: vi.fn(),
}));

vi.mock("../render-top-table.js", () => ({
  renderTopTable: vi.fn(),
}));

vi.mock("../render-pipeline-health-chart.js", () => ({
  renderPipelineHealthChart: renderPipelineHealthChartSpy,
}));

import { createMockJqXHRChainable } from "../../__tests__/helpers/mock-jquery.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const BASE_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button id="MetricsWindowDay"   class="MetricsWindowButton" data-window="day"   aria-pressed="true"></button>
    <button id="MetricsWindowWeek"  class="MetricsWindowButton" data-window="week"  aria-pressed="false"></button>
    <button id="MetricsWindowMonth" class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button id="MetricsWindowYear"  class="MetricsWindowButton" data-window="year"  aria-pressed="false"></button>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi"><table id="MetricsTopTableApi"><tbody></tbody></table></section>
    <section id="MetricsPanelUi"><table id="MetricsTopTableUi"><tbody></tbody></table></section>
    <section id="MetricsPanelDomain"><table id="MetricsTopTableDomain"><tbody></tbody></table></section>
    <svg id="MetricsPipelineHealthChart"></svg>
    <div id="MetricsErrorBanner" class="hidden"></div>
`;
const LEGEND_HTML = `<ul id="MetricsPipelineHealthLegend"></ul>`;
const PIPELINE_RESPONSE = { buckets: [] };

function mountDashboard({ withLegend }: { withLegend: boolean }): void {
  document.body.innerHTML = `${BASE_HTML}${withLegend ? LEGEND_HTML : ""}</main>`;
}

describe("metrics-dashboard Pipeline Health wiring", () => {
  beforeEach(() => {
    Object.defineProperty(document, "visibilityState", {
      value: "visible",
      configurable: true,
    });
    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchGroupedTimeseriesSpy.mockReset();
    fetchGaugesTimeseriesSpy.mockReset();
    renderPipelineHealthChartSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => createMockJqXHRChainable());
    fetchTopEventsSpy.mockImplementation(() => createMockJqXHRChainable());
    fetchGaugesTimeseriesSpy.mockImplementation(() =>
      createMockJqXHRChainable(),
    );
    fetchGroupedTimeseriesSpy.mockImplementation(() =>
      createMockJqXHRChainable({
        done: (callback: unknown) =>
          (callback as (response: unknown) => void)(PIPELINE_RESPONSE),
      }),
    );
    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  it("requests a window-wide floor without resolution and renders with the legend", () => {
    mountDashboard({ withLegend: true });
    initMetricsDashboard();

    expect(fetchGroupedTimeseriesSpy).toHaveBeenCalledTimes(1);
    const requestArgs = fetchGroupedTimeseriesSpy.mock.calls[0][0];
    expect(requestArgs.partitionByBucket).toBe(false);
    expect("resolution" in requestArgs).toBe(false);

    expect(renderPipelineHealthChartSpy).toHaveBeenCalledTimes(1);
    const renderArgs = renderPipelineHealthChartSpy.mock.calls[0][0];
    expect(renderArgs.legend).toBe(
      document.getElementById("MetricsPipelineHealthLegend"),
    );
  });

  it("skips the render without throwing when the legend element is missing", () => {
    mountDashboard({ withLegend: false });
    expect(() => initMetricsDashboard()).not.toThrow();
    expect(renderPipelineHealthChartSpy).not.toHaveBeenCalled();
  });
});

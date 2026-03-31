function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i += 1) {
    const char = text[i];
    const next = text[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && char === ',') {
      row.push(cell);
      cell = "";
      continue;
    }

    if (!inQuotes && (char === "\n" || char === "\r")) {
      if (char === "\r" && next === "\n") {
        i += 1;
      }
      row.push(cell);
      cell = "";
      if (row.length > 1 || row[0] !== "") {
        rows.push(row);
      }
      row = [];
      continue;
    }

    cell += char;
  }

  if (cell.length > 0 || row.length > 0) {
    row.push(cell);
    rows.push(row);
  }

  if (!rows.length) {
    return [];
  }

  const headers = rows[0].map((h) => h.trim());
  return rows.slice(1).map((r) => {
    const obj = {};
    headers.forEach((key, idx) => {
      obj[key] = (r[idx] || "").trim();
    });
    return obj;
  });
}

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function rankRows(rows) {
  return rows.map((row, idx) => ({ ...row, rank: idx + 1 }));
}

function attachSortableHeaders(tableId, state, renderFn) {
  const headers = document.querySelectorAll(`#${tableId} thead th`);
  headers.forEach((header) => {
    header.addEventListener("click", () => {
      const key = header.dataset.key;
      if (!key) {
        return;
      }

      if (state.sortKey === key) {
        state.sortDir = state.sortDir === "asc" ? "desc" : "asc";
      } else {
        state.sortKey = key;
        state.sortDir = header.dataset.type === "string" ? "asc" : "desc";
      }
      renderFn();
    });
  });
}

function sortRows(rows, sortKey, sortDir, type) {
  const direction = sortDir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    let av = a[sortKey];
    let bv = b[sortKey];

    if (type === "number") {
      av = toNumber(av);
      bv = toNumber(bv);
      if (av !== bv) {
        return (av - bv) * direction;
      }
      return String(a.contributor || a.repo).localeCompare(String(b.contributor || b.repo));
    }

    return String(av).localeCompare(String(bv)) * direction;
  });
}

function renderHighlights(overallRows, repoRows) {
  const topContributor = [...overallRows].sort((a, b) => toNumber(b.changed_lines_merged) - toNumber(a.changed_lines_merged))[0];

  const repoAgg = {};
  repoRows.forEach((row) => {
    const key = `${row.repo_owner}/${row.repo_name}`;
    if (!repoAgg[key]) {
      repoAgg[key] = {
        repo: key,
        prs_total: 0,
        prs_merged: 0,
        changed_lines_all: 0,
      };
    }
    repoAgg[key].prs_total += toNumber(row.prs_total);
    repoAgg[key].prs_merged += toNumber(row.prs_merged);
    repoAgg[key].changed_lines_all += toNumber(row.changed_lines_all);
  });

  const repos = Object.values(repoAgg);
  const topByChanges = [...repos].sort((a, b) => b.changed_lines_all - a.changed_lines_all)[0];
  const topByPrs = [...repos].sort((a, b) => b.prs_total - a.prs_total)[0];

  document.getElementById("topContributor").textContent = topContributor ? topContributor.contributor : "No data";
  document.getElementById("topContributorNote").textContent = topContributor
    ? `${topContributor.changed_lines_merged} merged changed lines, ${topContributor.prs_merged} merged PRs`
    : "No contributions found";

  document.getElementById("topRepoChanges").textContent = topByChanges ? topByChanges.repo : "No data";
  document.getElementById("topRepoChangesNote").textContent = topByChanges
    ? `${topByChanges.changed_lines_all} changed lines`
    : "No contributions found";

  document.getElementById("topRepoPrs").textContent = topByPrs ? topByPrs.repo : "No data";
  document.getElementById("topRepoPrsNote").textContent = topByPrs
    ? `${topByPrs.prs_total} PRs, ${topByPrs.prs_merged} merged`
    : "No contributions found";
}

function renderTable(tableId, rows, columns) {
  const tbody = document.querySelector(`#${tableId} tbody`);
  tbody.innerHTML = rows.map((row) => {
    const cells = columns.map((column) => `<td>${row[column]}</td>`).join("");
    return `<tr>${cells}</tr>`;
  }).join("");
}

function formatUtc(date) {
  if (!date) {
    return "Unavailable";
  }
  return `${new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "UTC",
  }).format(date)} UTC`;
}

function getNextScheduledUtc(now) {
  const hoursUtc = [7, 12, 17, 22];
  const current = new Date(now.getTime());
  current.setUTCSeconds(0, 0);

  for (const hour of hoursUtc) {
    const candidate = new Date(Date.UTC(
      current.getUTCFullYear(),
      current.getUTCMonth(),
      current.getUTCDate(),
      hour,
      0,
      0,
      0
    ));
    if (candidate > current) {
      return candidate;
    }
  }

  return new Date(Date.UTC(
    current.getUTCFullYear(),
    current.getUTCMonth(),
    current.getUTCDate() + 1,
    hoursUtc[0],
    0,
    0,
    0
  ));
}

async function fetchLastUpdated(paths) {
  const candidates = Array.isArray(paths) ? paths : [paths];
  for (const path of candidates) {
    try {
      const headResponse = await fetch(path, { method: "HEAD", cache: "no-store" });
      if (headResponse.ok) {
        const headModified = headResponse.headers.get("last-modified");
        if (headModified) {
          return new Date(headModified);
        }
      }

      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        continue;
      }
      const lastModified = response.headers.get("last-modified");
      if (lastModified) {
        return new Date(lastModified);
      }
    } catch (_error) {
      // Try next candidate.
    }
  }
  return null;
}

async function updateFooter() {
  const lastUpdatedEl = document.getElementById("lastUpdated");
  const nextUpdateEl = document.getElementById("nextUpdate");

  const [lastUpdated] = await Promise.all([
    fetchLastUpdated(["leaderboard.csv", "../leaderboard.csv"]),
  ]);

  const nextScheduled = getNextScheduledUtc(new Date());

  if (lastUpdatedEl) {
    lastUpdatedEl.textContent = formatUtc(lastUpdated);
  }
  if (nextUpdateEl) {
    nextUpdateEl.textContent = formatUtc(nextScheduled);
  }
}

async function loadCsv(paths) {
  const candidates = Array.isArray(paths) ? paths : [paths];
  const attempted = [];

  for (const path of candidates) {
    attempted.push(path);
    try {
      const response = await fetch(path, { cache: "no-store" });
      if (!response.ok) {
        continue;
      }
      const text = await response.text();
      return parseCsv(text);
    } catch (_error) {
      // Keep trying other paths.
    }
  }

  throw new Error(`Failed to load CSV. Tried: ${attempted.join(", ")}`);
}

(async function init() {
  try {
    if (window.location.protocol === "file:") {
      throw new Error(
        "This page is opened via file://. Most browsers block CSV fetches in this mode. " +
        "Run a local server and open http://localhost:8000/docs/index.html instead."
      );
    }

    const [overallRaw, repoRaw] = await Promise.all([
      loadCsv(["leaderboard.csv", "../leaderboard.csv"]),
      loadCsv(["repo_breakdown.csv", "../repo_breakdown.csv"]),
    ]);

    const overallBase = rankRows(overallRaw.map((row) => ({
      ...row,
      prs_total: toNumber(row.prs_total),
      prs_merged: toNumber(row.prs_merged),
      changed_lines_all: toNumber(row.changed_lines_all),
      changed_lines_merged: toNumber(row.changed_lines_merged),
      additions_merged: toNumber(row.additions_merged),
      deletions_merged: toNumber(row.deletions_merged),
    })));

    const repoBase = repoRaw.map((row) => ({
      ...row,
      repo: `${row.repo_owner}/${row.repo_name}`,
      prs_total: toNumber(row.prs_total),
      prs_merged: toNumber(row.prs_merged),
      changed_lines_all: toNumber(row.changed_lines_all),
      changed_lines_merged: toNumber(row.changed_lines_merged),
    }));

    renderHighlights(overallBase, repoBase);

    const overallState = {
      sortKey: "rank",
      sortDir: "asc",
      filter: "",
    };

    const repoState = {
      sortKey: "changed_lines_all",
      sortDir: "desc",
      filter: "",
    };

    const overallTypeByKey = {
      rank: "number",
      contributor: "string",
      prs_total: "number",
      prs_merged: "number",
      changed_lines_all: "number",
      changed_lines_merged: "number",
      additions_merged: "number",
      deletions_merged: "number",
    };

    const repoTypeByKey = {
      repo: "string",
      contributor: "string",
      prs_total: "number",
      prs_merged: "number",
      changed_lines_all: "number",
      changed_lines_merged: "number",
    };

    function renderOverall() {
      const filtered = overallBase.filter((row) => row.contributor.toLowerCase().includes(overallState.filter));
      const sorted = sortRows(filtered, overallState.sortKey, overallState.sortDir, overallTypeByKey[overallState.sortKey]);
      renderTable("overallTable", sorted, [
        "rank",
        "contributor",
        "prs_total",
        "prs_merged",
        "changed_lines_all",
        "changed_lines_merged",
        "additions_merged",
        "deletions_merged",
      ]);
    }

    function renderRepo() {
      const filtered = repoBase.filter((row) => {
        const needle = repoState.filter;
        return row.repo.toLowerCase().includes(needle) || row.contributor.toLowerCase().includes(needle);
      });
      const sorted = sortRows(filtered, repoState.sortKey, repoState.sortDir, repoTypeByKey[repoState.sortKey]);
      renderTable("repoTable", sorted, [
        "repo",
        "contributor",
        "prs_total",
        "prs_merged",
        "changed_lines_all",
        "changed_lines_merged",
      ]);
    }

    document.getElementById("overallFilter").addEventListener("input", (event) => {
      overallState.filter = event.target.value.trim().toLowerCase();
      renderOverall();
    });

    document.getElementById("repoFilter").addEventListener("input", (event) => {
      repoState.filter = event.target.value.trim().toLowerCase();
      renderRepo();
    });

    attachSortableHeaders("overallTable", overallState, renderOverall);
    attachSortableHeaders("repoTable", repoState, renderRepo);

    renderOverall();
    renderRepo();
    updateFooter();
  } catch (error) {
    const hero = document.querySelector(".hero");
    const message = document.createElement("p");
    message.textContent = `Could not load leaderboard data: ${error.message}`;
    message.style.color = "#ffd6a0";
    message.style.maxWidth = "70ch";
    hero.appendChild(message);
  }
}());

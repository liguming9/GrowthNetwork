(() => {
  "use strict";

  const DATA_URL = "./data/web_network.json";
  const PERSONAL_STROKE = "#7b2bc7";
  const PERSONAL_STORAGE_KEY = "growthNetwork.latestVisitorSession";
  const PERSONAL_HISTORY_KEY = "growthNetwork.visitorSessions";
  const canvas = document.getElementById("network-canvas");
  const context = canvas.getContext("2d", { alpha: false });
  const app = document.getElementById("app");
  const animationStage = document.getElementById("exhibition");
  const loadingMessage = document.getElementById("loading-message");
  const errorMessage = document.getElementById("error-message");
  const errorDetail = document.getElementById("error-detail");
  const controls = document.getElementById("controls");
  const playPauseButton = document.getElementById("play-pause");
  const restartButton = document.getElementById("restart");
  const speedSelect = document.getElementById("speed");
  const timelineInput = document.getElementById("timeline");
  const timeReadout = document.getElementById("time-readout");
  const onsiteVisitorReadout = document.getElementById("onsite-visitor-readout");
  const exhibitionPlayPauseButton = document.getElementById("exhibition-play-pause");
  const exhibitionRestartButton = document.getElementById("exhibition-restart");
  const exhibitionTimelineInput = document.getElementById("exhibition-timeline");
  const exhibitionReadout = document.getElementById("exhibition-readout");
  const fullscreenButton = document.getElementById("fullscreen");
  const labelsButton = document.getElementById("toggle-labels");
  const onsiteModeButton = document.getElementById("select-onsite");
  const exhibitionModeButton = document.getElementById("select-exhibition");
  const personalModeButton = document.getElementById("select-personal");
  const replayActiveButton = document.getElementById("replay-active");
  const pointerHint = document.getElementById("pointer-hint");
  const activeLayerBadge = document.getElementById("active-layer-badge");
  const metricVisitors = document.getElementById("metric-visitors");
  const metricBranches = document.getElementById("metric-branches");
  const metricEvents = document.getElementById("metric-events");
  const metricRoutes = document.getElementById("metric-routes");
  const metricDwell = document.getElementById("metric-dwell");
  const exhibitionDateStrip = document.getElementById("exhibition-date-strip");
  const dateTimelineViewport = document.getElementById("date-timeline-viewport");
  const dateTimelineTrack = document.getElementById("date-timeline-track");
  const timelineCurrentDate = document.getElementById("timeline-current-date");
  const timelineCurrentVisitors = document.getElementById("timeline-current-visitors");
  const personalTimelineGroup = document.getElementById("personal-timeline-group");
  const personalTimelineInput = document.getElementById("personal-timeline");
  const personalPlayPauseButton = document.getElementById("personal-play-pause");
  const personalRestartButton = document.getElementById("personal-restart");
  const personalStageReadout = document.getElementById("personal-stage-readout");
  const personalTimeReadout = document.getElementById("personal-time-readout");
  const personalOrderReadout = document.getElementById("personal-order-readout");
  const visitComplete = document.getElementById("visit-complete");
  const viewMyJourneyButton = document.getElementById("view-my-journey");
  const myJourneyModeButton = document.getElementById("mode-my-journey");
  const sharedSpaceModeButton = document.getElementById("mode-shared-space");
  const journeyView = document.getElementById("journey-view");
  const sharedView = document.getElementById("shared-view");
  const journeyReplayButton = document.getElementById("journey-replay-button");
  const sharedReplayButton = document.getElementById("shared-replay-button");
  const seeSharedSpaceButton = document.getElementById("see-shared-space");
  const viewMemoryButton = document.getElementById("view-memory-button");
  const journeyDate = document.getElementById("journey-date");
  const journeyVisitorId = document.getElementById("journey-visitor-id");
  const journeyOrder = document.getElementById("journey-order");
  const journeyTotalTime = document.getElementById("journey-total-time");
  const journeyLongestStop = document.getElementById("journey-longest-stop");
  const exhibitInfoButtons = [...document.querySelectorAll("[data-exhibit-info]")];
  const exhibitionInfoDialog = document.getElementById("exhibition-info-dialog");
  const exhibitionInfoIndex = document.getElementById("exhibition-info-index");
  const exhibitionInfoTitle = document.getElementById("exhibition-info-title");
  const exhibitionInfoImage = document.getElementById("exhibition-info-image");
  const exhibitionInfoDescription = document.getElementById("exhibition-info-description");
  const closeExhibitionInfoButton = document.getElementById("close-exhibition-info");
  const closeExhibitionInfoIcon = document.getElementById("close-exhibition-info-icon");

  const visitorTest = document.getElementById("visitor-test");
  const testWelcome = document.getElementById("test-welcome");
  const exhibitPicker = document.getElementById("exhibit-picker");
  const enterTestButton = document.getElementById("enter-test");
  const viewedCount = document.getElementById("viewed-count");
  const exhibitChoices = [...document.querySelectorAll(".exhibit-choice")];
  const exhibitDialog = document.getElementById("exhibit-dialog");
  const detailIndex = document.getElementById("detail-index");
  const detailTitle = document.getElementById("detail-title");
  const detailImage = document.getElementById("detail-image");
  const detailDescription = document.getElementById("detail-description");
  const detailDwellTime = document.getElementById("detail-dwell-time");
  const finishExhibitButton = document.getElementById("finish-exhibit");

  const exhibitContent = {
    Brain: {
      index: "Exhibit 01 / Neural control",
      image: "./assets/brain.png",
      alt: "White sculptural model of a brain",
      description: "The brain is the body's control centre. It receives and processes sensory information, supports thought and memory, and coordinates movement, emotion and many automatic functions.",
    },
    Eye: {
      index: "Exhibit 02 / Vision",
      image: "./assets/eye.png",
      alt: "White sculptural model of an eye",
      description: "The eye detects light and converts it into electrical signals. These signals travel through the optic nerve to the brain, where they are interpreted as vision.",
    },
    Heart: {
      index: "Exhibit 03 / Circulation",
      image: "./assets/heart.png",
      alt: "White sculptural model of a heart",
      description: "The heart is a muscular pump that circulates blood throughout the body. It delivers oxygen and nutrients to tissues and carries carbon dioxide and other waste products away.",
    },
    Lung: {
      index: "Exhibit 04 / Respiration",
      image: "./assets/lung.png",
      alt: "White sculptural model of lungs",
      description: "The lungs exchange gases between the body and the air. They move oxygen into the bloodstream and remove carbon dioxide when we breathe out.",
    },
  };

  const state = {
    data: null,
    branches: [],
    renderOrder: [],
    nodes: [],
    currentTime: 0,
    duration: 1,
    exhibitionTime: 0,
    exhibitionDuration: 1,
    speed: 1,
    playing: false,
    exhibitionPlaying: false,
    personalTime: 0,
    personalDuration: 1,
    personalPlaying: false,
    personalSession: null,
    personalJourney: null,
    experienceMode: "journey",
    activeLayer: "onsite",
    labelsVisible: true,
    previousFrame: null,
    cssWidth: 1,
    cssHeight: 1,
    dpr: 1,
    scale: 1,
    offsetX: 0,
    offsetY: 0,
    mobileRotated: false,
    pointerDriven: true,
    dateTicks: [],
    activeExhibitionDay: -1,
    visitorArrivalTimes: [],
  };

  const testState = {
    session: null,
    activeExhibitId: null,
    openedAt: 0,
    dwellTicker: null,
  };

  // A touch gesture represents relative time on mobile. The gesture remains
  // captured until it ends, then the following swipe is released to native
  // page scrolling once the selected growth layer has reached 100%.
  const mobileSwipeGesture = {
    tracking: false,
    directionLocked: false,
    startX: 0,
    startY: 0,
    lastY: 0,
  };

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function assert(condition, message) {
    if (!condition) {
      throw new Error(message);
    }
  }

  function createVisitorId() {
    const source = typeof crypto.randomUUID === "function"
      ? crypto.randomUUID().replaceAll("-", "")
      : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
    return `V-${source.slice(0, 6).toUpperCase()}`;
  }

  function createVisitorSession() {
    return {
      schemaVersion: 1,
      visitorId: createVisitorId(),
      startedAt: new Date().toISOString(),
      completedAt: null,
      order: [],
      dwellByNode: {},
      viewEvents: [],
    };
  }

  function persistVisitorSession(session) {
    try {
      localStorage.setItem(PERSONAL_STORAGE_KEY, JSON.stringify(session));
      const previous = JSON.parse(localStorage.getItem(PERSONAL_HISTORY_KEY) || "[]");
      const history = Array.isArray(previous) ? previous : [];
      history.push(session);
      localStorage.setItem(PERSONAL_HISTORY_KEY, JSON.stringify(history.slice(-50)));
    } catch (error) {
      console.warn("The visitor session could not be persisted locally", error);
    }
    // The supplied GrowthNetwork server validates the same record, keeps a
    // local JSONL backup and, when configured, uploads an independent JSON
    // file to the private visitor-data repository. A plain static server
    // remains a supported fallback through the browser-local copy above.
    window.fetch("/api/visitor-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(session),
    }).then((response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
    }).catch(() => {
      // The static-server fallback has no POST endpoint by design.
    });
  }

  function updatePickerProgress() {
    const session = testState.session;
    const viewed = session ? session.order.length : 0;
    viewedCount.textContent = `${viewed} / ${Object.keys(exhibitContent).length}`;
    for (const choice of exhibitChoices) {
      const nodeId = choice.dataset.exhibitId;
      const isViewed = Boolean(session?.order.includes(nodeId));
      choice.classList.toggle("is-viewed", isViewed);
      const status = choice.querySelector(".choice-status");
      status.textContent = isViewed
        ? `${Number(session.dwellByNode[nodeId] || 0).toFixed(1)}s recorded`
        : "Not viewed";
    }
  }

  function startVisitorTest() {
    testState.session = createVisitorSession();
    testState.activeExhibitId = null;
    testWelcome.hidden = true;
    exhibitPicker.hidden = false;
    updatePickerProgress();
    exhibitChoices[0]?.focus();
  }

  function openExhibit(nodeId) {
    const content = exhibitContent[nodeId];
    if (!content || !testState.session || exhibitDialog.open) {
      return;
    }
    testState.activeExhibitId = nodeId;
    testState.openedAt = performance.now();
    detailIndex.textContent = content.index;
    detailTitle.textContent = nodeId;
    detailImage.src = content.image;
    detailImage.alt = content.alt;
    detailDescription.textContent = content.description;
    detailDwellTime.textContent = "0.0s";
    const isFinalUnseenExhibit = testState.session.order.length === 3
      && !testState.session.order.includes(nodeId);
    finishExhibitButton.textContent = isFinalUnseenExhibit
      ? "Finish and reveal my trace"
      : "Finish viewing";
    exhibitDialog.showModal();
    testState.dwellTicker = window.setInterval(() => {
      const elapsed = (performance.now() - testState.openedAt) / 1000;
      detailDwellTime.textContent = `${elapsed.toFixed(1)}s`;
    }, 100);
  }

  function activatePersonalResult() {
    if (!state.data || !state.personalSession) {
      return;
    }
    preparePersonalJourney(state.personalSession);
    state.currentTime = state.duration;
    state.exhibitionTime = state.exhibitionDuration;
    state.personalTime = 0;
    state.playing = false;
    state.exhibitionPlaying = false;
    state.personalPlaying = false;
    state.pointerDriven = true;
    setActiveLayer("personal");
    window.requestAnimationFrame(() => {
      resizeCanvas();
      render(performance.now());
      updateControls();
    });
  }

  function completeVisitorTest() {
    const session = testState.session;
    if (!session || session.order.length !== Object.keys(exhibitContent).length) {
      return;
    }
    session.completedAt = new Date().toISOString();
    persistVisitorSession(session);
    state.personalSession = session;
    visitorTest.hidden = true;
    visitComplete.hidden = false;
    app.hidden = true;
    window.scrollTo({ top: 0, behavior: "auto" });
    updateVisitorFacingContent();
  }

  function formatRecordedDuration(seconds) {
    const safeSeconds = Math.max(0, Number(seconds) || 0);
    if (safeSeconds < 60) {
      return `${safeSeconds.toFixed(1)} seconds`;
    }
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = Math.round(safeSeconds - minutes * 60);
    return remainder > 0 ? `${minutes}m ${remainder}s` : `${minutes} min`;
  }

  function formatRecordedDate(isoValue) {
    const date = new Date(isoValue);
    if (Number.isNaN(date.getTime())) {
      return "Visit date unavailable";
    }
    return new Intl.DateTimeFormat("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(date);
  }

  function updateVisitorFacingContent() {
    const session = state.personalSession;
    if (!session) {
      journeyDate.textContent = "Complete the study to create a visit";
      journeyVisitorId.textContent = "Anonymous visitor";
      journeyOrder.textContent = "—";
      journeyTotalTime.textContent = "—";
      journeyLongestStop.textContent = "—";
      return;
    }

    const dwellEntries = session.order.map((nodeId) => [
      nodeId,
      Math.max(0, Number(session.dwellByNode[nodeId]) || 0),
    ]);
    const totalSeconds = dwellEntries.reduce((total, entry) => total + entry[1], 0);
    const longestStop = dwellEntries.reduce(
      (longest, entry) => entry[1] > longest[1] ? entry : longest,
      ["—", 0],
    );

    journeyDate.textContent = formatRecordedDate(session.completedAt || session.startedAt);
    journeyVisitorId.textContent = `Anonymous visitor · ${session.visitorId}`;
    journeyOrder.textContent = session.order.join(" → ");
    journeyTotalTime.textContent = formatRecordedDuration(totalSeconds);
    journeyLongestStop.textContent = longestStop[0] === "—"
      ? "—"
      : `${longestStop[0]} · ${formatRecordedDuration(longestStop[1])}`;
  }

  function setExperienceMode(mode) {
    const showJourney = mode !== "shared";
    state.experienceMode = showJourney ? "journey" : "shared";
    app.dataset.experienceMode = state.experienceMode;
    journeyView.hidden = !showJourney;
    sharedView.hidden = showJourney;
    myJourneyModeButton.classList.toggle("is-active", showJourney);
    sharedSpaceModeButton.classList.toggle("is-active", !showJourney);
    myJourneyModeButton.setAttribute("aria-pressed", String(showJourney));
    sharedSpaceModeButton.setAttribute("aria-pressed", String(!showJourney));

    if (showJourney && state.personalJourney) {
      setActiveLayer("personal");
    } else if (!showJourney) {
      setActiveLayer("onsite");
    }
  }

  function replayPersonalJourney() {
    if (!state.personalJourney) {
      return;
    }
    setExperienceMode("journey");
    setActiveLayer("personal");
    state.personalTime = 0;
    setPersonalPlaying(true);
    animationStage.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function enterPostVisitSite() {
    visitComplete.hidden = true;
    app.hidden = false;
    updateVisitorFacingContent();
    setExperienceMode("journey");
    window.scrollTo({ top: 0, behavior: "auto" });
    activatePersonalResult();
  }

  function bindPostVisitExperience() {
    viewMyJourneyButton.addEventListener("click", enterPostVisitSite);
    myJourneyModeButton.addEventListener("click", () => setExperienceMode("journey"));
    sharedSpaceModeButton.addEventListener("click", () => setExperienceMode("shared"));
    seeSharedSpaceButton.addEventListener("click", () => setExperienceMode("shared"));
    journeyReplayButton.addEventListener("click", replayPersonalJourney);
    sharedReplayButton.addEventListener("click", () => {
      setExperienceMode("shared");
      setActiveLayer("onsite");
      state.currentTime = 0;
      setPlaying(true);
      animationStage.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    viewMemoryButton.addEventListener("click", () => {
      setExperienceMode("shared");
      setActiveLayer("exhibition");
      animationStage.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    for (const button of exhibitInfoButtons) {
      button.addEventListener("click", () => {
        const nodeId = button.dataset.exhibitInfo;
        const content = exhibitContent[nodeId];
        if (!content) {
          return;
        }
        // This post-visit information view is intentionally separate from the
        // timed study dialog: opening it never changes the participant record.
        exhibitionInfoIndex.textContent = content.index;
        exhibitionInfoTitle.textContent = nodeId;
        exhibitionInfoImage.src = content.image;
        exhibitionInfoImage.alt = content.alt;
        exhibitionInfoDescription.textContent = content.description;
        exhibitionInfoDialog.showModal();
      });
    }
    closeExhibitionInfoButton.addEventListener("click", () => exhibitionInfoDialog.close());
    closeExhibitionInfoIcon.addEventListener("click", () => exhibitionInfoDialog.close());
  }

  function finishExhibit() {
    const session = testState.session;
    const nodeId = testState.activeExhibitId;
    if (!session || !nodeId || !exhibitDialog.open) {
      return;
    }
    if (testState.dwellTicker !== null) {
      window.clearInterval(testState.dwellTicker);
      testState.dwellTicker = null;
    }
    const elapsedSeconds = Math.max(0.1, (performance.now() - testState.openedAt) / 1000);
    const closedAt = new Date();
    const openedAt = new Date(closedAt.getTime() - elapsedSeconds * 1000);
    session.viewEvents.push({
      nodeId,
      order: session.viewEvents.length + 1,
      dwellSeconds: Number(elapsedSeconds.toFixed(3)),
      openedAt: openedAt.toISOString(),
      closedAt: closedAt.toISOString(),
    });
    session.dwellByNode[nodeId] = Number(
      (Number(session.dwellByNode[nodeId] || 0) + elapsedSeconds).toFixed(3),
    );
    if (!session.order.includes(nodeId)) {
      session.order.push(nodeId);
    }
    testState.activeExhibitId = null;
    exhibitDialog.close();
    updatePickerProgress();
    if (session.order.length === Object.keys(exhibitContent).length) {
      completeVisitorTest();
    }
  }

  function bindVisitorTest() {
    enterTestButton.addEventListener("click", startVisitorTest);
    for (const choice of exhibitChoices) {
      choice.addEventListener("click", () => openExhibit(choice.dataset.exhibitId));
    }
    finishExhibitButton.addEventListener("click", finishExhibit);
    exhibitDialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      finishExhibit();
    });
  }

  function validateData(data) {
    assert(data && typeof data === "object", "The JSON root must be an object.");
    assert(data.canvas && data.canvas.width > 0 && data.canvas.height > 0,
      "The JSON canvas size is missing or invalid.");
    assert(Array.isArray(data.nodes), "The JSON nodes array is missing.");
    assert(Array.isArray(data.branches) && data.branches.length > 0,
      "The JSON branches array is missing or empty.");
    assert(data.timeline && data.timeline.growthDuration > 0,
      "The JSON animation duration is missing or invalid.");

    for (const node of data.nodes) {
      assert(typeof node.id === "string" && node.id.length > 0,
        "Every node needs a non-empty id.");
      assert(node.organ && typeof node.organ === "object",
        `Node ${node.id} has no organ presentation data.`);
      assert(typeof node.organ.image === "string" && node.organ.image.length > 0,
        `Node ${node.id} has no organ image path.`);
      assert(node.organ.displayWidth > 0,
        `Node ${node.id} has an invalid organ display width.`);
    }

    const identifiers = new Set();
    for (const branch of data.branches) {
      assert(typeof branch.id === "string" && branch.id.length > 0,
        "Every branch needs a non-empty id.");
      assert(!identifiers.has(branch.id), `Duplicate branch id: ${branch.id}`);
      identifiers.add(branch.id);
      assert(Array.isArray(branch.points) && branch.points.length >= 2,
        `Branch ${branch.id} has fewer than two points.`);
      assert(Array.isArray(branch.widths) && branch.widths.length === branch.points.length,
        `Branch ${branch.id} has an invalid width profile.`);
      if (branch.level === 0) {
        assert(Array.isArray(branch.traversals) && branch.traversals.length > 0,
          `Main branch ${branch.id} has no timed visitor traversals.`);
        for (const event of branch.traversals) {
          assert(event.direction === "forward" || event.direction === "reverse",
            `Main branch ${branch.id} has an invalid traversal direction.`);
          assert(event.startTime >= 0 && event.duration > 0,
            `Main branch ${branch.id} has invalid traversal timing.`);
        }
      } else {
        assert(branch.growthDirection === "root-to-tip",
          `Branch ${branch.id} is not oriented from its root to its tip.`);
      }
    }
    for (const branch of data.branches) {
      assert(branch.parentId === null || identifiers.has(branch.parentId),
        `Branch ${branch.id} refers to missing parent ${branch.parentId}.`);
    }
  }

  function prepareBranch(branch) {
    const segmentLengths = [];
    const cumulativeLengths = [0];
    let length = 0;
    for (let index = 0; index < branch.points.length - 1; index += 1) {
      const first = branch.points[index];
      const second = branch.points[index + 1];
      const segmentLength = Math.hypot(second[0] - first[0], second[1] - first[1]);
      segmentLengths.push(segmentLength);
      length += segmentLength;
      cumulativeLengths.push(length);
    }
    return { ...branch, segmentLengths, cumulativeLengths, measuredLength: length };
  }

  function hashString(value) {
    let hash = 2166136261;
    for (let index = 0; index < value.length; index += 1) {
      hash ^= value.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  function seededRandom(seed) {
    let value = seed >>> 0;
    return () => {
      value += 0x6D2B79F5;
      let mixed = value;
      mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
      mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
      return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
    };
  }

  function prepareLocalPath(points) {
    const segmentLengths = [];
    const cumulativeLengths = [0];
    let measuredLength = 0;
    for (let index = 0; index < points.length - 1; index += 1) {
      const first = points[index];
      const second = points[index + 1];
      const segmentLength = Math.hypot(second[0] - first[0], second[1] - first[1]);
      segmentLengths.push(segmentLength);
      measuredLength += segmentLength;
      cumulativeLengths.push(measuredLength);
    }
    return { segmentLengths, cumulativeLengths, measuredLength };
  }

  // Build a deterministic parent-child vascular tree for each organ.  The
  // supplied image acts as an alpha mask later, so the red paths remain on the
  // visible anatomical form even when a terminal branch explores past an edge.
  function createOrganVessels(node) {
    const random = seededRandom(hashString(`GrowthNetwork-organ-${node.id}`));
    const organ = node.organ;
    const density = clamp(Number(organ.vesselDensity) || 1, 0.65, 1.25);
    const rootCount = Math.max(4, Math.round(Number(organ.vesselRoots) * density));
    const maximumLevel = clamp(Math.round(Number(organ.vesselDepth) || 3), 2, 4);
    const origin = Array.isArray(organ.vesselOrigin) ? organ.vesselOrigin : [0.5, 0.5];
    const vessels = [];
    let serial = 0;

    function addBranch(start, initialAngle, branchLength, level, parentId, startUnit) {
      const pointCount = 6 + Math.max(0, 2 - level);
      const points = [[start[0], start[1]]];
      let current = [start[0], start[1]];
      let direction = initialAngle;
      const stepLength = branchLength / (pointCount - 1);

      for (let index = 1; index < pointCount; index += 1) {
        // Low-frequency angular drift gives continuity without wave repetition.
        direction += (random() - 0.5) * (0.19 + level * 0.025);
        const next = [
          current[0] + Math.cos(direction) * stepLength,
          current[1] + Math.sin(direction) * stepLength,
        ];
        current = [clamp(next[0], -0.08, 1.08), clamp(next[1], -0.08, 1.08)];
        points.push(current);
      }

      const durationUnit = 0.082 + branchLength * 0.20 + level * 0.006;
      const id = `${node.id.toLowerCase()}-organ-vessel-${String(serial).padStart(3, "0")}`;
      serial += 1;
      const prepared = prepareLocalPath(points);
      const vessel = {
        id,
        parentId,
        level,
        points,
        width: (2.35 + 0.42 * Number(node.brightness || 1)) * (0.61 ** level),
        opacity: clamp(0.92 - level * 0.13, 0.46, 0.94),
        startUnit,
        durationUnit,
        ...prepared,
      };
      vessels.push(vessel);

      if (level >= maximumLevel) {
        return;
      }

      const extraChildChance = clamp((0.44 + (maximumLevel - level) * 0.08) * density, 0, 0.92);
      const childCount = 1 + (random() < extraChildChance ? 1 : 0);
      for (let childIndex = 0; childIndex < childCount; childIndex += 1) {
        const attachmentFraction = 0.58 + random() * 0.37;
        const attachmentIndex = clamp(
          Math.round(attachmentFraction * (points.length - 1)),
          1,
          points.length - 1,
        );
        const attachment = points[attachmentIndex];
        const previous = points[attachmentIndex - 1];
        const parentDirection = Math.atan2(
          attachment[1] - previous[1],
          attachment[0] - previous[0],
        );
        const side = childIndex % 2 === 0 ? -1 : 1;
        const childAngle = parentDirection + side * (0.38 + random() * 0.58);
        const childLength = branchLength * (0.52 + random() * 0.21);
        const childStart = startUnit + durationUnit * attachmentFraction + 0.012 + random() * 0.012;
        addBranch(attachment, childAngle, childLength, level + 1, id, childStart);
      }
    }

    for (let rootIndex = 0; rootIndex < rootCount; rootIndex += 1) {
      const evenAngle = (rootIndex / rootCount) * Math.PI * 2;
      const angle = evenAngle + (random() - 0.5) * 0.66;
      const start = [
        origin[0] + (random() - 0.5) * 0.025,
        origin[1] + (random() - 0.5) * 0.025,
      ];
      const length = 0.19 + random() * 0.14;
      addBranch(start, angle, length, 0, null, rootIndex * 0.009 + random() * 0.014);
    }
    return vessels.sort((first, second) => (
      second.level - first.level || first.startUnit - second.startUnit || first.id.localeCompare(second.id)
    ));
  }

  function prepareData(data) {
    state.data = data;
    state.branches = data.branches.map(prepareBranch);
    const arrivalByVisitor = new Map();
    for (const branch of data.branches) {
      for (const traversal of branch.traversals || []) {
        const visitorId = String(traversal.visitorId ?? "");
        const startTime = Number(traversal.startTime);
        if (!visitorId || !Number.isFinite(startTime)) {
          continue;
        }
        const previousArrival = arrivalByVisitor.get(visitorId);
        if (previousArrival === undefined || startTime < previousArrival) {
          arrivalByVisitor.set(visitorId, startTime);
        }
      }
    }
    state.visitorArrivalTimes = [...arrivalByVisitor.values()].sort((first, second) => first - second);
    state.nodes = data.nodes.map((node, index) => {
      const organVessels = createOrganVessels(node);
      const organScheduleEnd = Math.max(
        0.01,
        ...organVessels.map((vessel) => vessel.startUnit + vessel.durationUnit),
      );
      return {
        ...node,
        phase: index * 1.37,
        organVessels,
        organScheduleEnd,
        imageElement: null,
        vesselSurface: null,
        vesselContext: null,
      };
    });
    state.duration = Number(data.timeline.growthDuration);
    state.exhibitionDuration = state.duration;
    buildExhibitionTimeline();

    // Fine vessels are painted first, secondary branches next, and arteries last.
    // This reproduces the pygame hierarchy and keeps all six main routes readable.
    state.renderOrder = [...state.branches].sort((first, second) => {
      const firstRank = first.level === 0 ? Number.POSITIVE_INFINITY : -first.level;
      const secondRank = second.level === 0 ? Number.POSITIVE_INFINITY : -second.level;
      return firstRank - secondRank || first.birthTime - second.birthTime
        || first.id.localeCompare(second.id);
    });
    populateMetrics(data);
  }

  function collectPersonalBranchTree(root, branchById, childrenByParent, output) {
    if (output.has(root.id)) {
      return;
    }
    output.add(root.id);
    const children = childrenByParent.get(root.id) || [];
    for (const child of children) {
      collectPersonalBranchTree(child, branchById, childrenByParent, output);
    }
  }

  function preparePersonalJourney(session) {
    if (!state.data || !session || !Array.isArray(session.order)) {
      return;
    }
    const branchById = new Map(state.branches.map((branch) => [branch.id, branch]));
    const childrenByParent = new Map();
    for (const branch of state.branches) {
      if (branch.parentId === null) {
        continue;
      }
      const siblings = childrenByParent.get(branch.parentId) || [];
      siblings.push(branch);
      childrenByParent.set(branch.parentId, siblings);
    }

    const dwellValues = session.order.map(
      (nodeId) => Math.max(0.1, Number(session.dwellByNode[nodeId]) || 0.1),
    );
    const maximumDwell = Math.max(0.1, ...dwellValues);
    const visits = [];
    const routes = [];
    const dwellBranches = [];
    let cursor = 0;

    session.order.forEach((nodeId, visitIndex) => {
      const dwellSeconds = dwellValues[visitIndex];
      const dwellRatio = clamp(dwellSeconds / maximumDwell, 0.08, 1);
      // The playback remains readable for short test sessions, while longer
      // attention still occupies more of the personal timeline.
      const displayDuration = clamp(1.15 + Math.sqrt(dwellSeconds) * 0.86, 1.35, 8.5);
      const dwellStart = cursor;
      const dwellEnd = dwellStart + displayDuration;
      const availableRoots = state.branches
        .filter((branch) => branch.level === 1
          && branch.parentId === null
          && branch.type === "dwell_dendrite"
          && branch.sourceNode === nodeId)
        .sort((first, second) => {
          const firstScore = hashString(`${session.visitorId}:${nodeId}:${first.id}`);
          const secondScore = hashString(`${session.visitorId}:${nodeId}:${second.id}`);
          return firstScore - secondScore || first.id.localeCompare(second.id);
        });
      const rootCount = Math.min(
        availableRoots.length,
        Math.max(2, Math.round(2 + dwellRatio * 9)),
      );
      const selectedIds = new Set();
      for (const root of availableRoots.slice(0, rootCount)) {
        collectPersonalBranchTree(root, branchById, childrenByParent, selectedIds);
      }
      const selected = [...selectedIds]
        .map((branchId) => branchById.get(branchId))
        .filter(Boolean);
      const originalStart = selected.length > 0
        ? Math.min(...selected.map((branch) => branch.birthTime))
        : 0;
      const originalEnd = Math.max(
        originalStart + 1,
        ...selected.map((branch) => branch.birthTime + branch.duration),
      );
      const originalSpan = Math.max(0.001, originalEnd - originalStart);
      for (const branch of selected) {
        const relativeStart = (branch.birthTime - originalStart) / originalSpan;
        const scheduledStart = dwellStart + relativeStart * displayDuration * 0.76;
        const scaledDuration = clamp(
          branch.duration / originalSpan * displayDuration * 1.18,
          0.16,
          displayDuration * 0.54,
        );
        dwellBranches.push({
          branch,
          nodeId,
          startTime: scheduledStart,
          duration: Math.min(scaledDuration, Math.max(0.16, dwellEnd - scheduledStart)),
        });
      }
      visits.push({
        nodeId,
        startTime: dwellStart,
        endTime: dwellEnd,
        dwellSeconds,
        rootCount,
        branchCount: selected.length,
      });
      cursor = dwellEnd;

      const nextNodeId = session.order[visitIndex + 1];
      if (!nextNodeId) {
        return;
      }
      const mainBranch = state.branches.find((branch) => branch.level === 0
        && ((branch.sourceNode === nodeId && branch.targetNode === nextNodeId)
          || (branch.sourceNode === nextNodeId && branch.targetNode === nodeId)));
      if (!mainBranch) {
        console.warn(`No existing route connects ${nodeId} and ${nextNodeId}.`);
        return;
      }
      const routeDuration = clamp(1.2 + mainBranch.measuredLength / 920, 1.35, 2.35);
      routes.push({
        branch: mainBranch,
        fromNode: nodeId,
        toNode: nextNodeId,
        direction: mainBranch.sourceNode === nodeId ? "forward" : "reverse",
        startTime: cursor,
        duration: routeDuration,
        endTime: cursor + routeDuration,
      });
      cursor += routeDuration;
    });

    state.personalJourney = {
      visitorId: session.visitorId,
      sequence: [...session.order],
      visits,
      routes,
      dwellBranches,
      duration: Math.max(1, cursor),
      recordedDwell: dwellValues.reduce((total, value) => total + value, 0),
    };
    state.personalDuration = state.personalJourney.duration;
    state.personalTime = 0;
    personalTimelineGroup.hidden = false;
    personalOrderReadout.textContent = `${session.order.join("  \u2192  ")}  /  ${state.personalJourney.recordedDwell.toFixed(1)}s viewing`;
  }

  function populateMetrics(data) {
    const formatter = new Intl.NumberFormat("en-GB");
    const visitorFallback = Math.max(
      0,
      ...data.nodes.map((node) => Number(node.visitCount) || 0),
    );
    const dwellValues = data.nodes
      .map((node) => Number(node.averageDwell))
      .filter((value) => Number.isFinite(value));
    const meanDwell = dwellValues.length > 0
      ? dwellValues.reduce((total, value) => total + value, 0) / dwellValues.length
      : 0;
    const mainRoutes = data.branches.filter((branch) => branch.level === 0).length;
    const summary = data.summary || {};

    metricVisitors.textContent = formatter.format(
      Number(summary.visitorCount) || visitorFallback,
    );
    metricBranches.textContent = formatter.format(data.branches.length);
    metricEvents.textContent = formatter.format(Number(summary.visitorEvents) || 0);
    metricRoutes.textContent = formatter.format(Number(summary.mainRoutes) || mainRoutes);
    metricDwell.textContent = `${meanDwell.toFixed(1)}s`;
  }

  function buildExhibitionTimeline() {
    const dayCount = 30;
    const visitorDay = 10;
    dateTimelineTrack.replaceChildren();
    state.dateTicks = [];
    state.activeExhibitionDay = -1;

    for (let day = 1; day <= dayCount; day += 1) {
      const tick = document.createElement("button");
      const dayNumber = document.createElement("strong");
      const annotation = document.createElement("span");
      tick.type = "button";
      tick.className = "date-tick";
      tick.setAttribute("aria-label", `${day} July 2026${day === visitorDay ? ", your visit" : ""}`);
      dayNumber.textContent = String(day).padStart(2, "0");
      annotation.textContent = day === visitorDay
        ? "Your visit"
        : day === 1
          ? "July"
          : day === dayCount
            ? "End"
            : "";
      if (day === visitorDay) {
        tick.classList.add("is-visitor-date");
      }
      tick.append(dayNumber, annotation);
      tick.addEventListener("click", () => {
        state.exhibitionTime = (day - 1) / (dayCount - 1) * state.exhibitionDuration;
        state.playing = false;
        state.exhibitionPlaying = false;
        state.personalPlaying = false;
        state.activeExhibitionDay = -1;
        setActiveLayer("exhibition");
        render(performance.now());
      });
      dateTimelineTrack.append(tick);
      state.dateTicks.push(tick);
    }
  }

  function updateExhibitionDateTimeline() {
    if (!state.data || state.dateTicks.length === 0) {
      return;
    }
    const progress = clamp(state.exhibitionTime / state.exhibitionDuration, 0, 1);
    const activeIndex = clamp(
      Math.round(progress * (state.dateTicks.length - 1)),
      0,
      state.dateTicks.length - 1,
    );
    exhibitionDateStrip.classList.toggle(
      "is-controlling",
      state.activeLayer === "exhibition",
    );
    if (activeIndex === state.activeExhibitionDay) {
      return;
    }

    state.activeExhibitionDay = activeIndex;
    for (let index = 0; index < state.dateTicks.length; index += 1) {
      const tick = state.dateTicks[index];
      tick.classList.toggle("is-active", index === activeIndex);
      tick.classList.toggle("is-near", Math.abs(index - activeIndex) === 1);
      tick.setAttribute("aria-current", index === activeIndex ? "date" : "false");
      tick.setAttribute("aria-pressed", String(index === activeIndex));
    }
    const activeDay = activeIndex + 1;
    timelineCurrentDate.textContent = `${String(activeDay).padStart(2, "0")} July 2026`;
    const totalVisitors = Math.max(0, Number(state.data.summary?.visitorCount) || 0);
    const accumulatedVisitors = state.visitorArrivalTimes.length > 0
      ? state.visitorArrivalTimes.filter((arrivalTime) => (
        arrivalTime <= state.exhibitionTime + 0.0001
      )).length
      : state.dateTicks.length <= 1
        ? totalVisitors
        : Math.round(activeIndex / (state.dateTicks.length - 1) * totalVisitors);
    timelineCurrentVisitors.textContent = `${accumulatedVisitors} accumulated ${
      accumulatedVisitors === 1 ? "visitor" : "visitors"
    }`;

    const activeTick = state.dateTicks[activeIndex];
    const targetLeft = activeTick.offsetLeft + activeTick.offsetWidth * 0.5
      - dateTimelineViewport.clientWidth * 0.5;
    const maximumLeft = Math.max(
      0,
      dateTimelineViewport.scrollWidth - dateTimelineViewport.clientWidth,
    );
    dateTimelineViewport.scrollTo({
      left: clamp(targetLeft, 0, maximumLeft),
      behavior: state.exhibitionPlaying ? "smooth" : "auto",
    });
  }

  function loadImage(url, nodeId) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.decoding = "async";
      image.addEventListener("load", () => resolve(image), { once: true });
      image.addEventListener("error", () => {
        reject(new Error(`The organ image for ${nodeId} could not be loaded: ${url}`));
      }, { once: true });
      image.src = new URL(url, window.location.href).href;
    });
  }

  async function loadOrganAssets() {
    await Promise.all(state.nodes.map(async (node) => {
      const image = await loadImage(node.organ.image, node.id);
      const longestSide = 480;
      const aspect = image.naturalWidth / image.naturalHeight;
      const surface = document.createElement("canvas");
      if (aspect >= 1) {
        surface.width = longestSide;
        surface.height = Math.max(1, Math.round(longestSide / aspect));
      } else {
        surface.height = longestSide;
        surface.width = Math.max(1, Math.round(longestSide * aspect));
      }
      node.imageElement = image;
      node.imageAspect = aspect;
      node.vesselSurface = surface;
      node.vesselContext = surface.getContext("2d");
      if (!node.vesselContext) {
        throw new Error(`Canvas rendering is unavailable for the ${node.id} image.`);
      }
    }));
  }

  function resizeCanvas() {
    const bounds = canvas.getBoundingClientRect();
    const dpr = Math.min(3, Math.max(1, window.devicePixelRatio || 1));
    const pixelWidth = Math.max(1, Math.round(bounds.width * dpr));
    const pixelHeight = Math.max(1, Math.round(bounds.height * dpr));
    if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
    }
    state.cssWidth = Math.max(1, bounds.width);
    state.cssHeight = Math.max(1, bounds.height);
    state.dpr = dpr;
    state.activeExhibitionDay = -1;
    if (state.data) {
      state.mobileRotated = state.cssWidth < 780;
      if (state.mobileRotated) {
        // Turn the long horizontal route into a vertical mobile composition.
        // The original X axis runs from top to bottom after the 90° rotation.
        // A small, intentional horizontal crop lets the capillary structure
        // read at a useful size on narrow screens.
        state.scale = Math.min(
          state.cssHeight / state.data.canvas.width * 0.95,
          state.cssWidth / state.data.canvas.height * 1.08,
        );
        state.offsetX = state.cssWidth * 0.5
          + state.data.canvas.height * 0.5 * state.scale;
        state.offsetY = state.cssHeight * 0.5
          - state.data.canvas.width * 0.5 * state.scale;
        return;
      }
      // Reserve a clean editorial column for the title on wide screens, then
      // shift the proportional network into the right-hand exhibition field.
      // Mobile uses the full width because its title sits above the canvas.
      const networkWidthFraction = 0.68;
      state.scale = state.cssWidth / state.data.canvas.width * networkWidthFraction;
      state.offsetX = state.cssWidth * 0.30;
      state.offsetY = (state.cssHeight - state.data.canvas.height * state.scale) / 2;
    }
  }

  function branchOpacity(branch, pathFraction) {
    if (branch.level === 0 || pathFraction <= 0.70) {
      return branch.opacity;
    }
    const tipFactor = Math.max(0.14, ((1 - pathFraction) / 0.30) ** 0.48);
    return branch.opacity * tipFactor;
  }

  function collectiveAlpha(alpha) {
    // In the personal view the collective red field remains spatial context,
    // but recedes to 30% opacity so the overlapping purple trace is legible.
    return alpha * (state.activeLayer === "personal" ? 0.3 : 1);
  }

  function traversalContribution(event, pathFraction, transitionWindow) {
    const eventProgress = clamp(
      (state.currentTime - event.startTime) / Math.max(0.001, event.duration),
      0,
      1,
    );
    if (eventProgress <= 0) {
      return 0;
    }
    const requiredProgress = event.direction === "reverse"
      ? 1 - pathFraction
      : pathFraction;
    return clamp(
      (eventProgress - requiredProgress + transitionWindow) / transitionWindow,
      0,
      1,
    );
  }

  function drawDataDrivenMainBranch(branch) {
    const traversals = Array.isArray(branch.traversals) ? branch.traversals : [];
    if (traversals.length === 0 || branch.measuredLength <= 1e-9) {
      return false;
    }

    context.strokeStyle = state.data.style.mainStroke;
    context.lineCap = "round";
    context.lineJoin = "round";
    // Each original polyline segment is subdivided so an individual visitor's
    // moving front remains continuous. Every traversal reinforces the same
    // centreline; it never creates another parallel route.
    const subdivisions = 3;
    for (let index = 0; index < branch.segmentLengths.length; index += 1) {
      const segmentLength = branch.segmentLengths[index];
      if (segmentLength <= 1e-9) {
        continue;
      }
      const first = branch.points[index];
      const second = branch.points[index + 1];
      const transitionWindow = Math.max(
        0.008,
        segmentLength / branch.measuredLength / subdivisions,
      );
      for (let subdivision = 0; subdivision < subdivisions; subdivision += 1) {
        const localStart = subdivision / subdivisions;
        const localEnd = (subdivision + 1) / subdivisions;
        const localMiddle = (localStart + localEnd) * 0.5;
        const pathFraction = clamp(
          (branch.cumulativeLengths[index] + segmentLength * localMiddle)
            / branch.measuredLength,
          0,
          1,
        );
        const reinforcedCount = traversals.reduce(
          (total, event) => total
            + traversalContribution(event, pathFraction, transitionWindow),
          0,
        );
        if (reinforcedCount <= 0.001) {
          continue;
        }
        const reinforcementFraction = clamp(
          reinforcedCount / traversals.length,
          0,
          1,
        );
        const thicknessScale = 0.12 + 0.88 * Math.sqrt(reinforcementFraction);
        const finalWidth = branch.widths[index]
          + (branch.widths[index + 1] - branch.widths[index]) * localMiddle;
        const startPoint = [
          first[0] + (second[0] - first[0]) * localStart,
          first[1] + (second[1] - first[1]) * localStart,
        ];
        const endPoint = [
          first[0] + (second[0] - first[0]) * localEnd,
          first[1] + (second[1] - first[1]) * localEnd,
        ];

        context.globalAlpha = collectiveAlpha(
          branch.opacity * (0.55 + 0.45 * Math.sqrt(reinforcementFraction)),
        );
        context.lineWidth = Math.max(
          finalWidth * thicknessScale,
          0.82 / state.scale,
        );
        context.beginPath();
        context.moveTo(startPoint[0], startPoint[1]);
        context.lineTo(endPoint[0], endPoint[1]);
        context.stroke();
      }
    }
    return true;
  }

  function drawBranch(branch) {
    if (branch.level === 0 && drawDataDrivenMainBranch(branch)) {
      return;
    }
    const localTime = state.currentTime - branch.birthTime;
    if (localTime <= 0 || branch.measuredLength <= 1e-9) {
      return;
    }
    const progress = clamp(localTime / branch.duration, 0, 1);
    let remainingDistance = branch.measuredLength * progress;
    const colour = branch.level === 0
      ? state.data.style.mainStroke
      : state.data.style.branchStroke;

    context.strokeStyle = colour;
    context.lineCap = "round";
    context.lineJoin = "round";
    let activeTip = null;
    let activeTipWidth = 0;
    for (let index = 0; index < branch.segmentLengths.length; index += 1) {
      const segmentLength = branch.segmentLengths[index];
      if (remainingDistance <= 0 || segmentLength <= 1e-9) {
        break;
      }
      const visibleFraction = Math.min(1, remainingDistance / segmentLength);
      const first = branch.points[index];
      const second = branch.points[index + 1];
      const visibleEnd = [
        first[0] + (second[0] - first[0]) * visibleFraction,
        first[1] + (second[1] - first[1]) * visibleFraction,
      ];
      const width = branch.widths[index]
        + (branch.widths[index + 1] - branch.widths[index]) * visibleFraction * 0.5;
      const pathFraction = clamp(
        (branch.cumulativeLengths[index] + segmentLength * visibleFraction * 0.5)
          / branch.measuredLength,
        0,
        1,
      );

      context.globalAlpha = collectiveAlpha(branchOpacity(branch, pathFraction));
      context.lineWidth = Math.max(width, 0.82 / state.scale);
      context.beginPath();
      context.moveTo(first[0], first[1]);
      context.lineTo(visibleEnd[0], visibleEnd[1]);
      context.stroke();
      activeTip = visibleEnd;
      activeTipWidth = width;
      remainingDistance -= segmentLength;
      if (visibleFraction < 1) {
        break;
      }
    }

    if (progress < 0.999 && activeTip !== null && branch.level > 0) {
      // A compact leading point makes the root-to-tip direction legible without
      // adding particles or a separate decorative effect.
      context.globalAlpha = collectiveAlpha(Math.min(0.96, branch.opacity + 0.10));
      context.fillStyle = state.data.style.branchStroke;
      context.beginPath();
      context.arc(
        activeTip[0],
        activeTip[1],
        Math.max(0.55, activeTipWidth * 0.42),
        0,
        Math.PI * 2,
      );
      context.fill();
    }

    if (progress >= 0.999 && branch.level >= 2) {
      const terminal = branch.points[branch.points.length - 1];
      context.globalAlpha = collectiveAlpha(Math.min(0.94, branch.opacity + 0.08));
      context.fillStyle = state.data.style.branchStroke;
      context.beginPath();
      context.arc(
        terminal[0],
        terminal[1],
        Math.max(0.68, 1.05 / state.scale),
        0,
        Math.PI * 2,
      );
      context.fill();
    }
  }

  function drawExactPersonalPath(branch, progress, direction, widthScale, opacity) {
    const visibleProgress = clamp(progress, 0, 1);
    if (visibleProgress <= 0 || branch.measuredLength <= 1e-9) {
      return;
    }
    let remainingDistance = branch.measuredLength * visibleProgress;
    const reverse = direction === "reverse";
    context.strokeStyle = PERSONAL_STROKE;
    context.lineCap = "round";
    context.lineJoin = "round";
    context.globalAlpha = opacity;

    for (let step = 0; step < branch.segmentLengths.length; step += 1) {
      const index = reverse ? branch.segmentLengths.length - 1 - step : step;
      const segmentLength = branch.segmentLengths[index];
      if (remainingDistance <= 0 || segmentLength <= 1e-9) {
        break;
      }
      const visibleFraction = Math.min(1, remainingDistance / segmentLength);
      const first = reverse ? branch.points[index + 1] : branch.points[index];
      const second = reverse ? branch.points[index] : branch.points[index + 1];
      const firstWidth = reverse ? branch.widths[index + 1] : branch.widths[index];
      const secondWidth = reverse ? branch.widths[index] : branch.widths[index + 1];
      const visibleEnd = [
        first[0] + (second[0] - first[0]) * visibleFraction,
        first[1] + (second[1] - first[1]) * visibleFraction,
      ];
      const localWidth = firstWidth + (secondWidth - firstWidth) * visibleFraction * 0.5;
      context.lineWidth = Math.max(
        localWidth * widthScale,
        branch.level === 0 ? 1.65 / state.scale : 0.92 / state.scale,
      );
      context.beginPath();
      context.moveTo(first[0], first[1]);
      context.lineTo(visibleEnd[0], visibleEnd[1]);
      context.stroke();
      remainingDistance -= segmentLength;
      if (visibleFraction < 1) {
        break;
      }
    }
  }

  function drawPersonalJourney() {
    const journey = state.personalJourney;
    if (!journey || state.activeLayer !== "personal") {
      return;
    }
    // These overlays reference the prepared JSON branch objects directly. No
    // point is generated or displaced, so every purple line shares the exact
    // centreline of the collective red network beneath it.
    for (const entry of journey.dwellBranches) {
      const progress = clamp(
        (state.personalTime - entry.startTime) / Math.max(0.001, entry.duration),
        0,
        1,
      );
      drawExactPersonalPath(
        entry.branch,
        progress,
        "forward",
        1.08,
        clamp(entry.branch.opacity * 0.92, 0.42, 0.92),
      );
    }
    for (const route of journey.routes) {
      const progress = clamp(
        (state.personalTime - route.startTime) / Math.max(0.001, route.duration),
        0,
        1,
      );
      drawExactPersonalPath(route.branch, progress, route.direction, 0.72, 0.96);
    }
  }

  function drawOrganVessel(node, vessel) {
    const vesselContext = node.vesselContext;
    const exhibitionProgress = clamp(
      state.exhibitionTime / state.exhibitionDuration,
      0,
      1,
    );
    const birthProgress = vessel.startUnit / node.organScheduleEnd;
    const durationProgress = Math.max(
      0.01,
      vessel.durationUnit / node.organScheduleEnd,
    );
    const progress = clamp(
      (exhibitionProgress - birthProgress) / durationProgress,
      0,
      1,
    );
    if (progress <= 0 || vessel.measuredLength <= 1e-9) {
      return;
    }

    const surface = node.vesselSurface;
    const remainingLimit = vessel.measuredLength * progress;
    const displayWidth = Number(node.organ.displayWidth);
    const widthScale = surface.width / displayWidth;
    let remaining = remainingLimit;
    vesselContext.strokeStyle = vessel.level === 0
      ? (state.data.style.organMainStroke || "#2157a6")
      : (state.data.style.organBranchStroke || "#4f79c7");
    vesselContext.globalAlpha = vessel.opacity;
    vesselContext.lineWidth = Math.max(1.05, vessel.width * widthScale);
    vesselContext.lineCap = "round";
    vesselContext.lineJoin = "round";

    for (let index = 0; index < vessel.segmentLengths.length; index += 1) {
      const segmentLength = vessel.segmentLengths[index];
      if (remaining <= 0 || segmentLength <= 1e-9) {
        break;
      }
      const visibleFraction = Math.min(1, remaining / segmentLength);
      const first = vessel.points[index];
      const second = vessel.points[index + 1];
      const endX = first[0] + (second[0] - first[0]) * visibleFraction;
      const endY = first[1] + (second[1] - first[1]) * visibleFraction;
      vesselContext.beginPath();
      vesselContext.moveTo(first[0] * surface.width, first[1] * surface.height);
      vesselContext.lineTo(endX * surface.width, endY * surface.height);
      vesselContext.stroke();
      remaining -= segmentLength;
      if (visibleFraction < 1) {
        break;
      }
    }
  }

  function renderOrganVesselSurface(node) {
    const surface = node.vesselSurface;
    const vesselContext = node.vesselContext;
    vesselContext.setTransform(1, 0, 0, 1, 0, 0);
    vesselContext.globalCompositeOperation = "source-over";
    vesselContext.globalAlpha = 1;
    vesselContext.clearRect(0, 0, surface.width, surface.height);

    for (const vessel of node.organVessels) {
      drawOrganVessel(node, vessel);
    }

    // Use the organ PNG's transparency as a stencil. The blue exhibition-memory
    // layer can never spill into the white page around the anatomy.
    vesselContext.globalCompositeOperation = "destination-in";
    vesselContext.globalAlpha = 1;
    vesselContext.drawImage(node.imageElement, 0, 0, surface.width, surface.height);
    vesselContext.globalCompositeOperation = "source-over";
  }

  function drawNodes(frameTime) {
    const growthFinished = state.currentTime >= state.duration - 0.001
      && state.exhibitionTime >= state.exhibitionDuration - 0.001;
    for (const node of state.nodes) {
      if (!node.imageElement || !node.vesselSurface) {
        continue;
      }
      // Images are present from the first frame. Their red vascular overlay
      // follows the independent exhibition-accumulation clock, never the
      // horizontal pointer clock used by the current on-site visitor data.
      const breathing = growthFinished
        ? 1 + 0.008 * Math.sin(frameTime * 0.0015 + node.phase)
        : 1;
      const width = Number(node.organ.displayWidth) * breathing;
      const height = width / node.imageAspect;
      if (state.mobileRotated) {
        context.save();
        context.translate(node.x, node.y);
        context.rotate(-Math.PI / 2);
      }
      const nodeX = state.mobileRotated ? 0 : node.x;
      const nodeY = state.mobileRotated ? 0 : node.y;
      const left = nodeX - width * 0.5;
      const top = nodeY - height * 0.5;

      context.save();
      context.globalAlpha = 0.98;
      context.shadowColor = "rgba(48, 41, 34, 0.24)";
      context.shadowBlur = 17 / state.scale;
      context.shadowOffsetY = 8 / state.scale;
      context.drawImage(node.imageElement, left, top, width, height);
      context.restore();
      renderOrganVesselSurface(node);
      context.globalAlpha = 1;
      context.drawImage(node.vesselSurface, left, top, width, height);

      if (state.labelsVisible) {
        const fontSize = Math.max(13, 13 / state.scale);
        const labelY = top + height + 9 / state.scale;
        context.globalAlpha = 0.94;
        context.fillStyle = state.data.style.labelStroke;
        context.font = `400 ${fontSize}px Georgia, "Times New Roman", serif`;
        context.textAlign = "center";
        context.textBaseline = "top";
        context.fillText(node.id.toUpperCase(), nodeX, labelY);
        context.strokeStyle = state.data.style.labelStroke;
        context.lineWidth = Math.max(0.7, 0.85 / state.scale);
        context.beginPath();
        context.moveTo(nodeX - 12 / state.scale, labelY + fontSize + 8 / state.scale);
        context.lineTo(nodeX + 12 / state.scale, labelY + fontSize + 8 / state.scale);
        context.stroke();
      }
      if (state.mobileRotated) {
        context.restore();
      }
    }
  }

  function render(frameTime) {
    context.setTransform(1, 0, 0, 1, 0, 0);
    context.globalAlpha = 1;
    context.fillStyle = state.data?.style?.background || "#fbfaf7";
    context.fillRect(0, 0, canvas.width, canvas.height);
    if (!state.data) {
      return;
    }

    const transformScale = state.dpr * state.scale;
    if (state.mobileRotated) {
      context.setTransform(
        0,
        transformScale,
        -transformScale,
        0,
        state.dpr * state.offsetX,
        state.dpr * state.offsetY,
      );
    } else {
      context.setTransform(
        transformScale,
        0,
        0,
        transformScale,
        state.dpr * state.offsetX,
        state.dpr * state.offsetY,
      );
    }
    for (const branch of state.renderOrder) {
      drawBranch(branch);
    }
    drawPersonalJourney();
    drawNodes(frameTime);
    context.globalAlpha = 1;
  }

  function formatTime(seconds) {
    const safeSeconds = Math.max(0, seconds);
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = safeSeconds - minutes * 60;
    return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
  }

  function describePersonalStage() {
    const journey = state.personalJourney;
    if (!journey) {
      return "Complete the four-exhibit study";
    }
    const activeVisit = journey.visits.find((visit) => (
      state.personalTime >= visit.startTime && state.personalTime < visit.endTime
    ));
    if (activeVisit) {
      return `${activeVisit.nodeId} · ${activeVisit.dwellSeconds.toFixed(1)} seconds viewing`;
    }
    const activeRoute = journey.routes.find((route) => (
      state.personalTime >= route.startTime && state.personalTime < route.endTime
    ));
    if (activeRoute) {
      return `${activeRoute.fromNode} \u2192 ${activeRoute.toNode}`;
    }
    return state.personalTime >= journey.duration
      ? "Personal journey complete"
      : "Personal journey ready";
  }

  function updateControls() {
    const timelineValue = Math.round((state.currentTime / state.duration) * 1000);
    const exhibitionTimelineValue = Math.round(
      (state.exhibitionTime / state.exhibitionDuration) * 1000,
    );
    const personalTimelineValue = Math.round(
      (state.personalTime / state.personalDuration) * 1000,
    );
    timelineInput.value = String(clamp(timelineValue, 0, 1000));
    exhibitionTimelineInput.value = String(clamp(exhibitionTimelineValue, 0, 1000));
    personalTimelineInput.value = String(clamp(personalTimelineValue, 0, 1000));
    timeReadout.textContent = `${formatTime(state.currentTime)} / ${formatTime(state.duration)}`;
    personalTimeReadout.textContent = `${formatTime(state.personalTime)} / ${formatTime(state.personalDuration)}`;
    personalStageReadout.textContent = describePersonalStage();
    const traversalEvents = state.branches
      .filter((branch) => branch.level === 0)
      .flatMap((branch) => branch.traversals || []);
    const allVisitors = new Set(
      traversalEvents.map((event) => String(event.visitorId)),
    );
    const arrivedVisitors = new Set(
      traversalEvents
        .filter((event) => event.startTime <= state.currentTime)
        .map((event) => String(event.visitorId)),
    );
    onsiteVisitorReadout.textContent = `Visitors arrived ${arrivedVisitors.size} / ${allVisitors.size}`;
    exhibitionReadout.textContent = `Accumulation ${Math.round(
      clamp(exhibitionTimelineValue / 10, 0, 100),
    )}%`;
    playPauseButton.textContent = state.playing ? "Pause session" : "Play session";
    playPauseButton.setAttribute("aria-pressed", String(state.playing));
    exhibitionPlayPauseButton.textContent = state.exhibitionPlaying
      ? "Pause memory"
      : "Play memory";
    exhibitionPlayPauseButton.setAttribute(
      "aria-pressed",
      String(state.exhibitionPlaying),
    );
    personalPlayPauseButton.textContent = state.personalPlaying
      ? "Pause my journey"
      : "Play my journey";
    personalPlayPauseButton.setAttribute("aria-pressed", String(state.personalPlaying));
    const onsiteActive = state.activeLayer === "onsite";
    const exhibitionActive = state.activeLayer === "exhibition";
    const personalActive = state.activeLayer === "personal";
    onsiteModeButton.classList.toggle("is-active", onsiteActive);
    exhibitionModeButton.classList.toggle("is-active", exhibitionActive);
    personalModeButton.classList.toggle("is-active", personalActive);
    onsiteModeButton.setAttribute("aria-pressed", String(onsiteActive));
    exhibitionModeButton.setAttribute("aria-pressed", String(exhibitionActive));
    personalModeButton.setAttribute("aria-pressed", String(personalActive));
    personalModeButton.disabled = !state.personalJourney;
    app.dataset.activeLayer = state.activeLayer;
    activeLayerBadge.textContent = onsiteActive
      ? "On-site"
      : exhibitionActive
        ? "Exhibition memory"
        : "Your journey";
    const activeTimelineComplete = getActiveTimelineTime()
      >= getActiveTimelineDuration() - 0.0001;
    const pointerDirection = state.mobileRotated ? "vertically" : "horizontally";
    pointerHint.textContent = onsiteActive
      ? `Red session trace · Move ${pointerDirection} to follow visitors arriving at different times.`
      : `Blue exhibition memory · Move ${pointerDirection}, or select a date below.`;
    replayActiveButton.textContent = onsiteActive
      ? "↻ Replay Session"
      : "↻ Replay Exhibition Memory";
    if (personalActive) {
      pointerHint.textContent = `Purple personal trace · Move ${pointerDirection} to replay your viewing order and time.`;
      replayActiveButton.textContent = "↻ Replay My Journey";
    }
    if (state.mobileRotated) {
      const layerName = onsiteActive
        ? "Red on-site routes"
        : exhibitionActive
          ? "Blue exhibition memory"
          : "Purple personal trace";
      pointerHint.textContent = activeTimelineComplete
        ? `${layerName} complete / Swipe up again to continue down the page.`
        : `${layerName} / Swipe up to grow; swipe down to rewind.`;
      canvas.title = activeTimelineComplete
        ? "Growth complete. Swipe up to continue down the page."
        : "Swipe up to advance the selected growth layer";
    } else {
      canvas.title = "Move left to right to scrub the selected growth layer";
    }
    updateExhibitionDateTimeline();
  }

  function animate(frameTime) {
    if (state.previousFrame === null) {
      state.previousFrame = frameTime;
    }
    const elapsedMilliseconds = Math.min(100, frameTime - state.previousFrame);
    state.previousFrame = frameTime;
    if (state.playing && state.data) {
      state.currentTime += elapsedMilliseconds * 0.001 * state.speed;
      if (state.currentTime >= state.duration) {
        state.currentTime = state.duration;
        state.playing = false;
      }
    }
    if (state.exhibitionPlaying && state.data) {
      state.exhibitionTime += elapsedMilliseconds * 0.001 * state.speed;
      if (state.exhibitionTime >= state.exhibitionDuration) {
        state.exhibitionTime = state.exhibitionDuration;
        state.exhibitionPlaying = false;
      }
    }
    if (state.personalPlaying && state.personalJourney) {
      state.personalTime += elapsedMilliseconds * 0.001 * state.speed;
      if (state.personalTime >= state.personalDuration) {
        state.personalTime = state.personalDuration;
        state.personalPlaying = false;
      }
    }
    render(frameTime);
    if (state.data) {
      updateControls();
    }
    window.requestAnimationFrame(animate);
  }

  function setPlaying(playing) {
    state.playing = playing;
    state.pointerDriven = !playing;
    state.previousFrame = null;
    updateControls();
  }

  function setExhibitionPlaying(playing) {
    state.exhibitionPlaying = playing;
    state.previousFrame = null;
    updateControls();
  }

  function setPersonalPlaying(playing) {
    state.personalPlaying = playing;
    state.pointerDriven = !playing;
    state.previousFrame = null;
    updateControls();
  }

  function setActiveLayer(layer) {
    state.activeLayer = layer === "exhibition"
      ? "exhibition"
      : layer === "personal" && state.personalJourney
        ? "personal"
        : "onsite";
    updateControls();
  }

  function getActiveTimelineDuration() {
    if (state.activeLayer === "exhibition") {
      return state.exhibitionDuration;
    }
    if (state.activeLayer === "personal" && state.personalJourney) {
      return state.personalDuration;
    }
    return state.duration;
  }

  function getActiveTimelineTime() {
    if (state.activeLayer === "exhibition") {
      return state.exhibitionTime;
    }
    if (state.activeLayer === "personal" && state.personalJourney) {
      return state.personalTime;
    }
    return state.currentTime;
  }

  function setActiveTimelineTime(nextTime) {
    const duration = getActiveTimelineDuration();
    const time = clamp(nextTime, 0, duration);
    if (state.activeLayer === "exhibition") {
      state.exhibitionTime = time;
      state.exhibitionPlaying = false;
    } else if (state.activeLayer === "personal" && state.personalJourney) {
      state.personalTime = time;
      state.personalPlaying = false;
    } else {
      state.currentTime = time;
      state.playing = false;
    }
    state.pointerDriven = true;
    state.previousFrame = null;
  }

  function isInteractiveStageTarget(target) {
    return target instanceof Element
      && Boolean(target.closest("button, a, input, select, label"));
  }

  function beginMobileSwipe(event) {
    if (!state.mobileRotated
        || !state.data
        || event.touches.length !== 1
        || isInteractiveStageTarget(event.target)) {
      return;
    }
    // A fresh gesture that begins after completion belongs entirely to the
    // browser, allowing the page to scroll below the tall animation stage.
    if (getActiveTimelineTime() >= getActiveTimelineDuration() - 0.0001) {
      mobileSwipeGesture.tracking = false;
      return;
    }
    const touch = event.touches[0];
    mobileSwipeGesture.tracking = true;
    mobileSwipeGesture.directionLocked = false;
    mobileSwipeGesture.startX = touch.clientX;
    mobileSwipeGesture.startY = touch.clientY;
    mobileSwipeGesture.lastY = touch.clientY;
  }

  function moveMobileSwipe(event) {
    if (!mobileSwipeGesture.tracking
        || !state.mobileRotated
        || event.touches.length !== 1) {
      return;
    }
    const touch = event.touches[0];
    const totalX = touch.clientX - mobileSwipeGesture.startX;
    const totalY = touch.clientY - mobileSwipeGesture.startY;
    if (!mobileSwipeGesture.directionLocked) {
      if (Math.max(Math.abs(totalX), Math.abs(totalY)) < 5) {
        return;
      }
      if (Math.abs(totalX) > Math.abs(totalY)) {
        mobileSwipeGesture.tracking = false;
        return;
      }
      mobileSwipeGesture.directionLocked = true;
    }

    const upwardPixels = mobileSwipeGesture.lastY - touch.clientY;
    const currentTime = getActiveTimelineTime();
    // At time zero a downward gesture remains native, preventing a second
    // scroll trap at the beginning of the selected timeline.
    if (upwardPixels < 0 && currentTime <= 0.0001) {
      mobileSwipeGesture.tracking = false;
      return;
    }
    if (event.cancelable) {
      event.preventDefault();
    }
    mobileSwipeGesture.lastY = touch.clientY;
    const gestureDistance = Math.max(
      360,
      Math.min(720, canvas.getBoundingClientRect().height * 0.72),
    );
    const timeDelta = upwardPixels / gestureDistance
      * getActiveTimelineDuration();
    setActiveTimelineTime(currentTime + timeDelta);
    updateControls();
  }

  function endMobileSwipe() {
    mobileSwipeGesture.tracking = false;
    mobileSwipeGesture.directionLocked = false;
  }

  function scrubFromPointer(clientX, clientY) {
    if (!state.data) {
      return;
    }
    const bounds = canvas.getBoundingClientRect();
    const rawPointerPosition = state.mobileRotated
      ? clamp((clientY - bounds.top) / bounds.height, 0, 1)
      : clamp((clientX - bounds.left) / bounds.width, 0, 1);
    // A small edge snap makes the complete temporal range reachable even when
    // the browser reserves a few pixels at the viewport edge for its own UI.
    const pointerPosition = rawPointerPosition <= 0.012
      ? 0
      : rawPointerPosition >= 0.988
        ? 1
        : rawPointerPosition;
    if (state.activeLayer === "exhibition") {
      state.exhibitionTime = pointerPosition * state.exhibitionDuration;
      state.exhibitionPlaying = false;
    } else if (state.activeLayer === "personal" && state.personalJourney) {
      state.personalTime = pointerPosition * state.personalDuration;
      state.personalPlaying = false;
    } else {
      state.currentTime = pointerPosition * state.duration;
      state.playing = false;
    }
    state.pointerDriven = true;
    state.previousFrame = null;
    updateControls();
  }

  function scrubFromAnimationStage(event) {
    // Buttons retain normal click behaviour; all non-interactive editorial
    // layers (including the title) participate in the spatial timeline.
    if (isInteractiveStageTarget(event.target)) {
      return;
    }
    // Touch uses relative swipe distance on mobile. Applying this absolute
    // pointer mapping as well would make the timeline jump on touch-down.
    if (state.mobileRotated && event.pointerType === "touch") {
      return;
    }
    if (state.mobileRotated) {
      const bounds = canvas.getBoundingClientRect();
      if (event.clientY < bounds.top || event.clientY > bounds.bottom) {
        return;
      }
    }
    scrubFromPointer(event.clientX, event.clientY);
  }

  function bindControls() {
    playPauseButton.addEventListener("click", () => {
      setActiveLayer("onsite");
      if (!state.playing && state.currentTime >= state.duration) {
        state.currentTime = 0;
      }
      setPlaying(!state.playing);
    });
    restartButton.addEventListener("click", () => {
      setActiveLayer("onsite");
      state.currentTime = 0;
      setPlaying(false);
    });
    speedSelect.addEventListener("change", () => {
      state.speed = Number(speedSelect.value);
    });
    timelineInput.addEventListener("input", () => {
      setActiveLayer("onsite");
      state.currentTime = Number(timelineInput.value) / 1000 * state.duration;
      state.playing = false;
      state.pointerDriven = false;
      state.previousFrame = null;
      render(performance.now());
      updateControls();
    });
    exhibitionPlayPauseButton.addEventListener("click", () => {
      setActiveLayer("exhibition");
      if (!state.exhibitionPlaying
          && state.exhibitionTime >= state.exhibitionDuration) {
        state.exhibitionTime = 0;
      }
      setExhibitionPlaying(!state.exhibitionPlaying);
    });
    exhibitionRestartButton.addEventListener("click", () => {
      setActiveLayer("exhibition");
      state.exhibitionTime = 0;
      setExhibitionPlaying(false);
    });
    exhibitionTimelineInput.addEventListener("input", () => {
      setActiveLayer("exhibition");
      state.exhibitionTime = Number(exhibitionTimelineInput.value) / 1000
        * state.exhibitionDuration;
      state.exhibitionPlaying = false;
      state.previousFrame = null;
      render(performance.now());
      updateControls();
    });
    personalPlayPauseButton.addEventListener("click", () => {
      if (!state.personalJourney) {
        return;
      }
      setActiveLayer("personal");
      if (!state.personalPlaying && state.personalTime >= state.personalDuration) {
        state.personalTime = 0;
      }
      setPersonalPlaying(!state.personalPlaying);
    });
    personalRestartButton.addEventListener("click", () => {
      if (!state.personalJourney) {
        return;
      }
      setActiveLayer("personal");
      state.personalTime = 0;
      setPersonalPlaying(false);
    });
    personalTimelineInput.addEventListener("input", () => {
      if (!state.personalJourney) {
        return;
      }
      setActiveLayer("personal");
      state.personalTime = Number(personalTimelineInput.value) / 1000
        * state.personalDuration;
      state.personalPlaying = false;
      state.pointerDriven = false;
      state.previousFrame = null;
      render(performance.now());
      updateControls();
    });
    fullscreenButton.addEventListener("click", async () => {
      try {
        if (document.fullscreenElement) {
          await document.exitFullscreen();
        } else {
          await app.requestFullscreen();
        }
      } catch (error) {
        console.warn("Fullscreen is unavailable", error);
        fullscreenButton.textContent = "Fullscreen unavailable";
        fullscreenButton.disabled = true;
      }
    });
    document.addEventListener("fullscreenchange", () => {
      fullscreenButton.textContent = document.fullscreenElement
        ? "Exit fullscreen"
        : "Fullscreen";
      resizeCanvas();
    });
    labelsButton.addEventListener("click", () => {
      state.labelsVisible = !state.labelsVisible;
      labelsButton.textContent = state.labelsVisible ? "Hide labels" : "Show labels";
      labelsButton.setAttribute("aria-pressed", String(state.labelsVisible));
    });

    onsiteModeButton.addEventListener("click", () => {
      setActiveLayer("onsite");
    });
    exhibitionModeButton.addEventListener("click", () => {
      setActiveLayer("exhibition");
    });
    personalModeButton.addEventListener("click", () => {
      if (state.personalJourney) {
        setActiveLayer("personal");
      }
    });
    replayActiveButton.addEventListener("click", () => {
      if (!state.data) {
        return;
      }
      if (state.activeLayer === "exhibition") {
        state.exhibitionTime = 0;
        setExhibitionPlaying(true);
      } else if (state.activeLayer === "personal" && state.personalJourney) {
        state.personalTime = 0;
        setPersonalPlaying(true);
      } else {
        state.currentTime = 0;
        setPlaying(true);
      }
    });

    // The complete exhibition stage is the desktop spatial timeline. Listening
    // on the stage, rather than only the canvas underneath it, prevents the
    // editorial title from blocking the leftmost (time zero) interaction area.
    // Each layer retains its own clock, so switching never erases the other.
    animationStage.addEventListener("pointermove", scrubFromAnimationStage, {
      passive: true,
    });
    animationStage.addEventListener("pointerdown", scrubFromAnimationStage, {
      passive: true,
    });
    animationStage.addEventListener("touchstart", beginMobileSwipe, {
      passive: true,
    });
    animationStage.addEventListener("touchmove", moveMobileSwipe, {
      passive: false,
    });
    animationStage.addEventListener("touchend", endMobileSwipe, {
      passive: true,
    });
    animationStage.addEventListener("touchcancel", endMobileSwipe, {
      passive: true,
    });
  }

  function showError(message) {
    state.playing = false;
    state.exhibitionPlaying = false;
    state.personalPlaying = false;
    loadingMessage.hidden = true;
    controls.hidden = true;
    errorDetail.textContent = message;
    errorMessage.hidden = false;
  }

  async function loadNetwork() {
    try {
      const response = await fetch(DATA_URL, { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} while loading ${DATA_URL}`);
      }
      const data = await response.json();
      validateData(data);
      prepareData(data);
      await loadOrganAssets();
      resizeCanvas();
      state.playing = false;
      state.exhibitionPlaying = false;
      state.personalPlaying = false;
      if (state.personalSession) {
        preparePersonalJourney(state.personalSession);
        state.currentTime = state.duration;
        state.exhibitionTime = state.exhibitionDuration;
        state.personalTime = 0;
        state.activeLayer = "personal";
      } else {
        state.currentTime = 0;
        state.exhibitionTime = 0;
        state.personalTime = 0;
        state.activeLayer = "onsite";
      }
      state.pointerDriven = true;
      loadingMessage.hidden = true;
      errorMessage.hidden = true;
      controls.hidden = false;
      updateControls();
    } catch (error) {
      const detail = error instanceof Error ? error.message : String(error);
      showError(`${detail} Run: python -m http.server 8000`);
    }
  }

  bindVisitorTest();
  bindPostVisitExperience();
  bindControls();
  new ResizeObserver(resizeCanvas).observe(app);
  window.addEventListener("resize", resizeCanvas, { passive: true });
  resizeCanvas();
  window.requestAnimationFrame(animate);
  loadNetwork();
})();

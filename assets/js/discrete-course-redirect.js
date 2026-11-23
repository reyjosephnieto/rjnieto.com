(() => {
  "use strict";

  const landingPaths = new Set(["/teaching/", "/teaching"]);
  const legacyPaths = new Set([
    "/teaching/bulsu/discrete-math/",
    "/teaching/bulsu/discrete-structures/",
    "/teaching/bulsu/discrete-mathematics/"
  ]);
  const aliases = {
    "the-course": "logistics",
    "tentative-course-outline": "course-outline",
    "primary-textbook": "course-outline",
    "printable-lecture-notes": "course-outline",
    "respect-for-learning": "course-policies"
  };
  const logisticsSections = new Set([
    "logistics",
    "no-class-saturdays",
    "class-format",
    "assessment",
    "assessment-dates",
    "mathematical-corrections",
    "final-examination-exemption",
    "problem-sheets",
    "course-policies",
    "about-me"
  ]);

  const redirectSection = () => {
    const location = window.location;
    const path = location.pathname.replace(/\/index\.html$/, "/");
    const isLanding = landingPaths.has(path);
    const isLegacy = legacyPaths.has(path.endsWith("/") ? path : `${path}/`);
    if (!isLanding && !isLegacy) return;

    const originalFragment = location.hash.slice(1);
    let fragment = originalFragment;
    try {
      fragment = decodeURIComponent(fragment);
    } catch {
      // Preserve malformed or unfamiliar fragments instead of rejecting a URL.
    }
    const hasAlias = Object.prototype.hasOwnProperty.call(aliases, fragment);
    if (hasAlias) fragment = aliases[fragment];

    let destinationPath = "/teaching/";
    if (fragment === "changelog") {
      destinationPath = "/teaching/changelog/";
    } else if (logisticsSections.has(fragment)) {
      destinationPath = "/teaching/logistics/";
    } else if (isLanding) {
      return;
    }

    const destination = new URL(destinationPath, location.origin);
    destination.search = location.search;
    destination.hash = hasAlias || destinationPath !== "/teaching/"
      ? fragment : originalFragment;
    location.replace(destination.href);
  };

  window.addEventListener("hashchange", redirectSection);
  redirectSection();
})();

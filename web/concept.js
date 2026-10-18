const requestedConcept = new URLSearchParams(location.search).get("concept");
const concept = ["siemens", "twin", "executive", "slate", "boardroom"].includes(requestedConcept)
  ? requestedConcept
  : "executive";

document.documentElement.dataset.concept = concept;

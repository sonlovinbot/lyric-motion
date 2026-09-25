/* Vietnamese labels are applied after all expression packs register, before the editor starts.
   The label table (app/vietnamese_labels.json) is inlined by build.py in place of the placeholder below.
   Internal IDs and project JSON remain language independent. */
(() => {
  'use strict';
  const L = /*VI_LABELS*/null;
  if (!L) return;
  for (const group of J.GROUP_KEYS) {
    const names = (L.groups || {})[group] || {};
    for (const key of J.order(group)) {
      const item = J.registry(group)[key];
      if (item && names[key]) item.name = names[key];
    }
  }
  for (const [key, s] of Object.entries(L.styles || {})) if (J.STYLES[key]) { J.STYLES[key].name = s.name; J.STYLES[key].desc = s.desc; }
  for (const [key, name] of Object.entries(L.moods || {})) if (J.MOODS[key]) J.MOODS[key].name = name;
  if (L.sample) J.SAMPLE_LYRICS = L.sample;
})();

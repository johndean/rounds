/**
 * UI store — IMPLEMENTATION.md §14 (Tweaks panel) drives most of this.
 *  - theme:    light | dark
 *  - brand:    vin | vspn
 *  - density:  comfortable | compact
 *  - slideRailMode: focus | filter   (editor SlideRail segmented control)
 *  - focusedSlideId: id | null       (F1/F2 closures from §15)
 *  - aiFlagOverlays: boolean         (editor flag-overlay toggle)
 *  - statusBarVisible: boolean       (editor sticky-bottom debug bar)
 *  - classifyBackend: gemini_dev | vertex_ai  (Settings → Discrepancy classification)
 *  - classifyModel:  string                    (model id from CLASSIFY_MODELS_GEMINI/VERTEX)
 */
import { defineStore } from 'pinia';
import { ref, watch } from 'vue';

export type Theme = 'light' | 'dark';
export type Brand = 'vin' | 'vspn';
export type Density = 'comfortable' | 'compact';
export type SlideRailMode = 'focus' | 'filter';
export type ClassifyBackend = 'gemini_dev' | 'vertex_ai';

const STORAGE_KEY = 'rounds_ui_v1';

interface Persisted {
  theme: Theme;
  brand: Brand;
  density: Density;
  slideRailMode: SlideRailMode;
  aiFlagOverlays: boolean;
  statusBarVisible: boolean;
  classifyBackend: ClassifyBackend;
  classifyModel: string;
}

function loadPersisted(): Partial<Persisted> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) as Partial<Persisted> : {};
  } catch { return {}; }
}

export const useUiStore = defineStore('ui', () => {
  const persisted = loadPersisted();

  const theme = ref<Theme>(persisted.theme ?? 'light');
  const brand = ref<Brand>(persisted.brand ?? 'vin');
  const density = ref<Density>(persisted.density ?? 'comfortable');
  const slideRailMode = ref<SlideRailMode>(persisted.slideRailMode ?? 'focus');
  const aiFlagOverlays = ref<boolean>(persisted.aiFlagOverlays ?? true);
  const statusBarVisible = ref<boolean>(persisted.statusBarVisible ?? false);
  const classifyBackend = ref<ClassifyBackend>(persisted.classifyBackend ?? 'gemini_dev');
  const classifyModel = ref<string>(persisted.classifyModel ?? 'gemini-2.5-flash-lite');

  const focusedSlideId = ref<string | null>(null);  // session-scoped; not persisted

  function setTheme(value: Theme) {
    theme.value = value;
    document.documentElement.dataset.theme = value;
  }
  function setBrand(value: Brand) {
    brand.value = value;
    document.documentElement.dataset.brand = value;
  }
  function setDensity(value: Density) {
    density.value = value;
    document.documentElement.dataset.density = value;
  }
  function clearFocus() { focusedSlideId.value = null; }   // F1 / F2 closure helper

  // Initial DOM sync
  setTheme(theme.value);
  setBrand(brand.value);
  setDensity(density.value);

  // Persist on any change to durable fields
  watch(
    [theme, brand, density, slideRailMode, aiFlagOverlays, statusBarVisible, classifyBackend, classifyModel],
    () => {
      const snapshot: Persisted = {
        theme: theme.value,
        brand: brand.value,
        density: density.value,
        slideRailMode: slideRailMode.value,
        aiFlagOverlays: aiFlagOverlays.value,
        statusBarVisible: statusBarVisible.value,
        classifyBackend: classifyBackend.value,
        classifyModel: classifyModel.value,
      };
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot)); } catch { /* quota or private mode */ }
    },
    { deep: false },
  );

  return {
    theme, brand, density, slideRailMode, aiFlagOverlays, statusBarVisible,
    classifyBackend, classifyModel, focusedSlideId,
    setTheme, setBrand, setDensity, clearFocus,
  };
});

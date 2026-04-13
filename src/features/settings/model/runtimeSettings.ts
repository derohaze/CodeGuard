import { useCallback, useEffect, useRef, useState } from "react";
import {
  getRuntimeSettings,
  updateRuntimeSettings,
  type RuntimeSettings,
  type UpdateRuntimeSettingsPayload,
} from "@/shared/api/security";

export const SIDEBAR_COLLAPSED_STORAGE_KEY = "codeguard.sidebar.collapsed";

export const DEFAULT_RUNTIME_SETTINGS: RuntimeSettings = {
  defaultPreset: "balanced",
  defaultScanMode: "deep",
  autoOpenResults: true,
  rememberSidebarState: true,
  motionProfile: "fluid",
  theme: "light",
  surfaceContrast: "soft",
  remediationMaxAttempts: 3,
  remediationReuseExplanation: true,
  externalIngestionMaxRps: 10,
  externalIngestionRetryAttempts: 3,
  externalIngestionBackoffSeconds: 0.5,
  updatedAt: new Date(0).toISOString(),
};

export function useRuntimeSettings() {
  const [settings, setSettings] = useState<RuntimeSettings>(DEFAULT_RUNTIME_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const settingsRef = useRef(settings);

  useEffect(() => {
    settingsRef.current = settings;
  }, [settings]);

  useEffect(() => {
    let isCancelled = false;
    const load = async () => {
      try {
        const fetched = await getRuntimeSettings();
        if (!isCancelled) {
          setSettings(fetched);
        }
      } catch {
        if (!isCancelled) {
          setSettings(DEFAULT_RUNTIME_SETTINGS);
        }
      } finally {
        if (!isCancelled) {
          setIsLoading(false);
        }
      }
    };

    void load();
    return () => {
      isCancelled = true;
    };
  }, []);

  const patchSettings = useCallback(async (patch: UpdateRuntimeSettingsPayload) => {
    const previous = settingsRef.current;
    const optimistic = {
      ...previous,
      ...patch,
    };
    settingsRef.current = optimistic;
    setSettings(optimistic);
    setIsSaving(true);
    try {
      const persisted = await updateRuntimeSettings(patch);
      settingsRef.current = persisted;
      setSettings(persisted);
      return persisted;
    } catch (error) {
      settingsRef.current = previous;
      setSettings(previous);
      throw error;
    } finally {
      setIsSaving(false);
    }
  }, []);

  return {
    settings,
    isLoading,
    isSaving,
    patchSettings,
    setSettings,
  };
}

export function resolveMotionDuration(baseDuration: number, profile: RuntimeSettings["motionProfile"]) {
  if (profile === "instant") return 0.01;
  if (profile === "reduced") return Math.max(0.05, baseDuration * 0.5);
  return baseDuration;
}

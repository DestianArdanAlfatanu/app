import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useApi(path, deps = [], enabled = true) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tick, setTick] = useState(0);
  const reload = useCallback(() => setTick((t) => t + 1), []);
  useEffect(() => {
    if (!enabled || !path) { setLoading(false); return; }
    let alive = true;
    setLoading(true);
    api.get(path).then((r) => { if (alive) { setData(r.data); setError(null); } })
      .catch((e) => { if (alive) setError(e); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, enabled, ...deps]);
  return { data, loading, error, reload, setData };
}

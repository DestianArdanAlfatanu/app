import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";

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
      .catch((e) => {
        if (!alive) return;
        setError(e);
        // 401 sudah diarahkan ke halaman login oleh interceptor; error lain ditampilkan (satu toast per endpoint).
        if (e?.response?.status !== 401) toast.error(errMsg(e), { id: `load:${path}` });
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, enabled, ...deps]);
  return { data, loading, error, reload, setData };
}

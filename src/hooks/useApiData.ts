import { useState, useEffect } from "react";
import { getDataVersion } from "../data/mock";

export function useApiData() {
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let checks = 0;
    const interval = setInterval(() => {
      checks++;
      if (getDataVersion() > 0 || checks > 10) {
        setLoaded(true);
        clearInterval(interval);
      }
    }, 300);
    return () => clearInterval(interval);
  }, []);
  return loaded;
}

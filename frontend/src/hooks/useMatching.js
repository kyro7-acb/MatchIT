import { useState, useCallback } from "react";
import { api } from "../utils/api";

export function useMatching() {
  const [step, setStep]               = useState("idle"); // idle|ledger_pending|ready|uploading|matching|done
  const [sessionId, setSessionId]     = useState(null);
  const [invoices, setInvoices]       = useState([]);
  const [ledgerEntries, setLedger]    = useState([]);
  const [result, setResult]           = useState(null);
  const [error, setError]             = useState(null);
  const [progress, setProgress]       = useState("");

  const reset = useCallback(() => {
    setStep("idle");
    setSessionId(null);
    setInvoices([]);
    setLedger([]);
    setResult(null);
    setError(null);
    setProgress("");
  }, []);

  const dismissError = useCallback(() => setError(null), []);

  /* On failure, go back to the step the user was on so they can retry
     (e.g. pick a different ledger file) without losing the session. */
  const fail = useCallback((e, backTo) => {
    setError(e.message);
    setProgress("");
    setStep(backTo);
  }, []);

  const uploadInvoices = useCallback(async (files) => {
    setError(null);
    setStep("uploading");
    setProgress("Uploading and extracting invoices…");
    try {
      const res = await api.uploadInvoices(files);
      setSessionId(res.session_id);
      setInvoices(res.items);
      setProgress(`Extracted ${res.count} invoice(s). Now upload the ledger.`);
      setStep("ledger_pending");
      return res.session_id;
    } catch (e) {
      fail(e, "idle");
    }
  }, [fail]);

  const uploadLedger = useCallback(async (sid, files) => {
    setError(null);
    setStep("uploading");
    setProgress("Uploading and extracting ledger entries…");
    try {
      const res = await api.uploadLedger(sid, files);
      setLedger(res.items);
      setProgress(`Extracted ${res.count} ledger entry/entries. Ready to match.`);
      setStep("ready");
      return res;
    } catch (e) {
      fail(e, "ledger_pending");
    }
  }, [fail]);

  const runMatch = useCallback(async (sid) => {
    setError(null);
    setStep("matching");
    setProgress("");
    try {
      const res = await api.runMatch(sid);
      setResult(res);
      setStep("done");
    } catch (e) {
      fail(e, "ready");
    }
  }, [fail]);

  const overrideMatch = useCallback(async (matchId, status, note) => {
    await api.overrideMatch(matchId, status, note);
    // Refresh result
    if (sessionId) {
      const updated = await api.getResult(sessionId);
      setResult(updated);
    }
  }, [sessionId]);

  return {
    step, sessionId, invoices, ledgerEntries,
    result, error, progress,
    uploadInvoices, uploadLedger, runMatch, overrideMatch, reset, dismissError,
  };
}

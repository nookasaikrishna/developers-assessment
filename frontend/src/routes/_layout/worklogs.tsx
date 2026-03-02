import axios from "axios"
import { createFileRoute } from "@tanstack/react-router"
import { useEffect, useState } from "react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import useAuth from "@/hooks/useAuth"

const API_BASE = "http://localhost:8000/api/v1"

function getAuthHeaders() {
  const token = localStorage.getItem("access_token")
  return { Authorization: `Bearer ${token}` }
}

export const Route = createFileRoute("/_layout/worklogs")({
  component: WorklogsPage,
  head: () => ({
    meta: [{ title: "Worklogs - FastAPI Cloud" }],
  }),
})

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

function WorklogsPage() {
  const { user: currentUser } = useAuth()
  const isAdmin = currentUser?.is_superuser ?? false

  const [worklogs, setWorklogs] = useState<any[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // date range filter
  const [startDate, setStartDate] = useState("")
  const [endDate, setEndDate] = useState("")

  // status filter tab: "ALL" | "UNREMITTED" | "REMITTED"
  const [activeFilter, setActiveFilter] = useState("ALL")

  // pagination
  const [page, setPage] = useState(1)
  const PAGE_SIZE = 10

  // ------------------------------------------------------------------
  // Detail dialog state
  // ------------------------------------------------------------------
  const [selectedWorklog, setSelectedWorklog] = useState<any | null>(null)
  const [detailEntries, setDetailEntries] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [showDetail, setShowDetail] = useState(false)

  // Log time form (inside detail dialog)
  const [logDesc, setLogDesc] = useState("")
  const [logHours, setLogHours] = useState("")
  const [logRate, setLogRate] = useState("")
  const [logSubmitting, setLogSubmitting] = useState(false)
  const [showLogForm, setShowLogForm] = useState(false)

  // ------------------------------------------------------------------
  // New worklog dialog (freelancers only)
  // ------------------------------------------------------------------
  const [showNewWorklog, setShowNewWorklog] = useState(false)
  const [newTaskName, setNewTaskName] = useState("")
  const [newWlSubmitting, setNewWlSubmitting] = useState(false)

  // ------------------------------------------------------------------
  // Payment review dialog (admin only)
  // ------------------------------------------------------------------
  const [showPayment, setShowPayment] = useState(false)
  const [excludedIds, setExcludedIds] = useState<Set<string>>(new Set())
  const [excludedUsers, setExcludedUsers] = useState<Set<string>>(new Set())
  const [paymentLoading, setPaymentLoading] = useState(false)
  const [payPeriodStart, setPayPeriodStart] = useState("")
  const [payPeriodEnd, setPayPeriodEnd] = useState("")

  // -------------------------------------------------------------------------
  // Fetch worklogs
  // -------------------------------------------------------------------------
  async function fetchWorklogs() {
    setIsLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (startDate) params.startDate = startDate
      if (endDate) params.endDate = endDate
      if (activeFilter !== "ALL") params.remittanceStatus = activeFilter

      const response = await axios.get(`${API_BASE}/list-all-worklogs`, {
        headers: getAuthHeaders(),
        params,
      })
      setWorklogs(response.data.data ?? [])
      setPage(1)
    } catch (err: any) {
      setError("Failed to load worklogs. Please try again.")
      console.error(err)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    fetchWorklogs()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeFilter])

  // -------------------------------------------------------------------------
  // Worklog detail
  // -------------------------------------------------------------------------
  async function openDetail(wl: any) {
    setSelectedWorklog(wl)
    setShowDetail(true)
    setDetailLoading(true)
    setDetailEntries([])
    setShowLogForm(false)
    setLogDesc("")
    setLogHours("")
    setLogRate("")
    try {
      const response = await axios.get(`${API_BASE}/worklogs/${wl.id}`, {
        headers: getAuthHeaders(),
      })
      setDetailEntries(response.data.time_entries ?? [])
    } catch (err: any) {
      console.error(err)
      setDetailEntries([])
    } finally {
      setDetailLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Log time entry
  // -------------------------------------------------------------------------
  async function submitTimeEntry() {
    if (!selectedWorklog) return
    if (!logDesc.trim()) { toast.error("Description is required."); return }
    const hrs = parseFloat(logHours)
    const rate = parseFloat(logRate)
    if (!logHours || isNaN(hrs) || hrs <= 0) { toast.error("Enter valid hours (> 0)."); return }
    if (!logRate || isNaN(rate) || rate <= 0) { toast.error("Enter a valid hourly rate (> 0)."); return }

    setLogSubmitting(true)
    try {
      await axios.post(
        `${API_BASE}/worklogs/${selectedWorklog.id}/time-entries`,
        { description: logDesc.trim(), hours: hrs, hourly_rate: rate },
        { headers: getAuthHeaders() },
      )
      toast.success("Time entry logged.")
      setLogDesc("")
      setLogHours("")
      setLogRate("")
      setShowLogForm(false)
      // Refresh entries and worklog list
      const response = await axios.get(`${API_BASE}/worklogs/${selectedWorklog.id}`, {
        headers: getAuthHeaders(),
      })
      setDetailEntries(response.data.time_entries ?? [])
      fetchWorklogs()
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Failed to log time. Please try again."
      toast.error(msg)
      console.error(err)
    } finally {
      setLogSubmitting(false)
    }
  }

  // -------------------------------------------------------------------------
  // Create new worklog
  // -------------------------------------------------------------------------
  async function submitNewWorklog() {
    if (!newTaskName.trim()) { toast.error("Task name is required."); return }
    setNewWlSubmitting(true)
    try {
      await axios.post(
        `${API_BASE}/worklogs`,
        { task_name: newTaskName.trim() },
        { headers: getAuthHeaders() },
      )
      toast.success("Worklog created.")
      setNewTaskName("")
      setShowNewWorklog(false)
      fetchWorklogs()
    } catch (err: any) {
      const msg = err?.response?.data?.detail ?? "Failed to create worklog."
      toast.error(msg)
      console.error(err)
    } finally {
      setNewWlSubmitting(false)
    }
  }

  // -------------------------------------------------------------------------
  // Payment helpers (admin only)
  // -------------------------------------------------------------------------
  const unremittedWorklogs = worklogs.filter((wl) => wl.status === "UNREMITTED")

  function toggleExcludeWorklog(id: string) {
    setExcludedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  function toggleExcludeUser(userId: string) {
    setExcludedUsers((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) next.delete(userId)
      else next.add(userId)
      return next
    })
  }

  const selectedForPayment = unremittedWorklogs.filter(
    (wl) => !excludedIds.has(wl.id) && !excludedUsers.has(wl.user_id),
  )

  const byFreelancer: Record<string, any[]> = {}
  for (const wl of selectedForPayment) {
    if (!byFreelancer[wl.user_id]) byFreelancer[wl.user_id] = []
    byFreelancer[wl.user_id].push(wl)
  }

  function openPaymentDialog() {
    setExcludedIds(new Set())
    setExcludedUsers(new Set())
    const today = new Date().toISOString().slice(0, 10)
    const monthStart = new Date(new Date().getFullYear(), new Date().getMonth(), 1)
      .toISOString()
      .slice(0, 10)
    setPayPeriodStart(monthStart)
    setPayPeriodEnd(today)
    setShowPayment(true)
  }

  async function confirmPayment() {
    if (selectedForPayment.length === 0) { toast.error("No worklogs selected."); return }
    if (!payPeriodStart || !payPeriodEnd) { toast.error("Set both period dates."); return }
    setPaymentLoading(true)
    try {
      await axios.post(
        `${API_BASE}/generate-remittances-for-all-users`,
        {
          worklog_ids: selectedForPayment.map((wl) => wl.id),
          period_start: new Date(payPeriodStart).toISOString(),
          period_end: new Date(payPeriodEnd).toISOString(),
        },
        { headers: getAuthHeaders() },
      )
      toast.success(
        `Payment processed for ${Object.keys(byFreelancer).length} freelancer(s).`,
      )
      setShowPayment(false)
      fetchWorklogs()
    } catch (err: any) {
      toast.error(err?.response?.data?.detail ?? "Payment failed.")
      console.error(err)
    } finally {
      setPaymentLoading(false)
    }
  }

  // -------------------------------------------------------------------------
  // Pagination
  // -------------------------------------------------------------------------
  const totalPages = Math.ceil(worklogs.length / PAGE_SIZE)
  const displayedWorklogs = worklogs.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)

  // Does the current user own this worklog and can they still log time?
  function canLogTime(wl: any) {
    if (!wl) return false
    return wl.status === "UNREMITTED" && wl.user_id === currentUser?.id
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">
            {isAdmin ? "Worklogs" : "My Worklogs"}
          </h1>
          <p className="text-muted-foreground">
            {isAdmin
              ? "Review freelancer time logs and process payments"
              : "Track your work and log time against tasks"}
          </p>
        </div>
        <div className="flex gap-2">
          {/* All users can create a worklog */}
          <Button variant="outline" onClick={() => { setNewTaskName(""); setShowNewWorklog(true) }}>
            + New Worklog
          </Button>
          {/* Only admin can process payments */}
          {isAdmin && (
            <Button onClick={openPaymentDialog} disabled={unremittedWorklogs.length === 0}>
              Process Payment
            </Button>
          )}
        </div>
      </div>

      {/* Filter row */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
        {/* Status filter tabs */}
        <div className="flex gap-1 rounded-lg border p-1 w-fit">
          {["ALL", "UNREMITTED", "REMITTED"].map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => setActiveFilter(tab)}
              className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeFilter === tab
                  ? "bg-primary text-primary-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab === "ALL" ? "All" : tab === "UNREMITTED" ? "Unpaid" : "Paid"}
            </button>
          ))}
        </div>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <Input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="w-40"
            aria-label="Start date filter"
          />
          <span className="text-muted-foreground text-sm">to</span>
          <Input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="w-40"
            aria-label="End date filter"
          />
          <Button variant="outline" size="sm" onClick={fetchWorklogs}>
            Apply
          </Button>
          {(startDate || endDate) && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setStartDate(""); setEndDate("") }}
            >
              Clear
            </Button>
          )}
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="py-12 text-center text-muted-foreground">Loading worklogs…</div>
      ) : error ? (
        <div className="py-12 text-center text-destructive">{error}</div>
      ) : worklogs.length === 0 ? (
        <div className="py-12 text-center text-muted-foreground">
          No worklogs found. {!isAdmin && "Click \"+ New Worklog\" to get started."}
        </div>
      ) : (
        <>
          <div className="rounded-md border overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left font-medium">Task</th>
                  {isAdmin && (
                    <th className="px-4 py-3 text-left font-medium">Freelancer</th>
                  )}
                  <th className="px-4 py-3 text-right font-medium">Earnings</th>
                  <th className="px-4 py-3 text-left font-medium">Status</th>
                  <th className="px-4 py-3 text-left font-medium">Created At</th>
                  <th className="px-4 py-3 text-left font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {displayedWorklogs.map((wl: any, idx: number) => (
                  <tr
                    key={wl.id}
                    className={idx % 2 === 0 ? "bg-background" : "bg-muted/20"}
                  >
                    <td className="px-4 py-3 font-medium">{wl.task_name}</td>
                    {isAdmin && (
                      <td className="px-4 py-3">
                        <div>{wl.freelancer_name ?? "—"}</div>
                        <div className="text-xs text-muted-foreground">
                          {wl.freelancer_email}
                        </div>
                      </td>
                    )}
                    <td className="px-4 py-3 text-right font-mono">
                      ${wl.total_earnings.toFixed(2)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={wl.status === "REMITTED" ? "default" : "secondary"}>
                        {wl.status === "REMITTED" ? "Paid" : "Unpaid"}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground text-xs">
                      {wl.created_at}
                    </td>
                    <td className="px-4 py-3">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => openDetail(wl)}
                      >
                        {canLogTime(wl) ? "View / Log Time" : "View"}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * PAGE_SIZE + 1}–
                {Math.min(page * PAGE_SIZE, worklogs.length)} of {worklogs.length}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* New Worklog Dialog                                                  */}
      {/* ------------------------------------------------------------------ */}
      <Dialog open={showNewWorklog} onOpenChange={setShowNewWorklog}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>New Worklog</DialogTitle>
            <DialogDescription>
              Create a worklog for a task. You can log individual time entries after.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-3 py-2">
            <Label htmlFor="task-name">Task name</Label>
            <Input
              id="task-name"
              placeholder="e.g. Homepage Redesign"
              value={newTaskName}
              onChange={(e) => setNewTaskName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") submitNewWorklog() }}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowNewWorklog(false)}
              disabled={newWlSubmitting}
            >
              Cancel
            </Button>
            <Button onClick={submitNewWorklog} disabled={newWlSubmitting || !newTaskName.trim()}>
              {newWlSubmitting ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------------------------ */}
      {/* Worklog Detail Dialog                                               */}
      {/* ------------------------------------------------------------------ */}
      <Dialog open={showDetail} onOpenChange={setShowDetail}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{selectedWorklog?.task_name}</DialogTitle>
            <DialogDescription>
              {isAdmin && (
                <>
                  Freelancer:{" "}
                  {selectedWorklog?.freelancer_name ?? selectedWorklog?.freelancer_email}
                  &nbsp;·&nbsp;
                </>
              )}
              Total earnings:{" "}
              <span className="font-semibold">
                ${selectedWorklog?.total_earnings?.toFixed(2)}
              </span>
              &nbsp;·&nbsp;
              <Badge
                variant={selectedWorklog?.status === "REMITTED" ? "default" : "secondary"}
              >
                {selectedWorklog?.status === "REMITTED" ? "Paid" : "Unpaid"}
              </Badge>
            </DialogDescription>
          </DialogHeader>

          {/* Time entries table */}
          {detailLoading ? (
            <div className="py-8 text-center text-muted-foreground">
              Loading time entries…
            </div>
          ) : detailEntries.length === 0 ? (
            <div className="py-6 text-center text-muted-foreground">
              No time entries yet.{" "}
              {canLogTime(selectedWorklog) && "Use the form below to log your first entry."}
            </div>
          ) : (
            <div className="overflow-auto max-h-64">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">Description</th>
                    <th className="px-3 py-2 text-right font-medium">Hours</th>
                    <th className="px-3 py-2 text-right font-medium">Rate</th>
                    <th className="px-3 py-2 text-right font-medium">Amount</th>
                    <th className="px-3 py-2 text-left font-medium">Recorded At</th>
                    <th className="px-3 py-2 text-left font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {detailEntries.map((entry: any, idx: number) => (
                    <tr
                      key={entry.id}
                      className={`${idx % 2 === 0 ? "bg-background" : "bg-muted/20"} ${!entry.is_active ? "opacity-50" : ""}`}
                    >
                      <td className="px-3 py-2">{entry.description}</td>
                      <td className="px-3 py-2 text-right font-mono">{entry.hours}h</td>
                      <td className="px-3 py-2 text-right font-mono">
                        ${entry.hourly_rate}/h
                      </td>
                      <td className="px-3 py-2 text-right font-mono">
                        ${entry.amount.toFixed(2)}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {entry.recorded_at}
                      </td>
                      <td className="px-3 py-2">
                        {entry.is_active ? (
                          <Badge variant="default">Active</Badge>
                        ) : (
                          <Badge variant="destructive">Deducted</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Log time section — only for the owner of an unpaid worklog */}
          {canLogTime(selectedWorklog) && (
            <div className="border-t pt-4">
              {!showLogForm ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowLogForm(true)}
                >
                  + Log Time
                </Button>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm font-medium">Log a time entry</p>
                  <div className="grid gap-2">
                    <Label htmlFor="log-desc">Description</Label>
                    <Input
                      id="log-desc"
                      placeholder="e.g. Implemented login page"
                      value={logDesc}
                      onChange={(e) => setLogDesc(e.target.value)}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-2">
                      <Label htmlFor="log-hours">Hours worked</Label>
                      <Input
                        id="log-hours"
                        type="number"
                        min="0.25"
                        max="24"
                        step="0.25"
                        placeholder="e.g. 3.5"
                        value={logHours}
                        onChange={(e) => setLogHours(e.target.value)}
                      />
                    </div>
                    <div className="grid gap-2">
                      <Label htmlFor="log-rate">Hourly rate ($)</Label>
                      <Input
                        id="log-rate"
                        type="number"
                        min="1"
                        step="0.01"
                        placeholder="e.g. 85"
                        value={logRate}
                        onChange={(e) => setLogRate(e.target.value)}
                      />
                    </div>
                  </div>
                  {logHours && logRate && !isNaN(parseFloat(logHours)) && !isNaN(parseFloat(logRate)) && (
                    <p className="text-sm text-muted-foreground">
                      Amount: <span className="font-semibold text-foreground">
                        ${(parseFloat(logHours) * parseFloat(logRate)).toFixed(2)}
                      </span>
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={submitTimeEntry}
                      disabled={logSubmitting}
                    >
                      {logSubmitting ? "Saving…" : "Save Entry"}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setShowLogForm(false)}
                      disabled={logSubmitting}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ------------------------------------------------------------------ */}
      {/* Payment Review Dialog (admin only)                                  */}
      {/* ------------------------------------------------------------------ */}
      <Dialog open={showPayment} onOpenChange={setShowPayment}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Review & Confirm Payment</DialogTitle>
            <DialogDescription>
              Uncheck any worklogs or freelancers you want to exclude from this batch.
            </DialogDescription>
          </DialogHeader>

          {/* Billing period */}
          <div className="flex items-center gap-3 py-2">
            <span className="text-sm font-medium w-28 shrink-0">Billing period</span>
            <Input
              type="date"
              value={payPeriodStart}
              onChange={(e) => setPayPeriodStart(e.target.value)}
              className="w-40"
              aria-label="Period start"
            />
            <span className="text-muted-foreground text-sm">to</span>
            <Input
              type="date"
              value={payPeriodEnd}
              onChange={(e) => setPayPeriodEnd(e.target.value)}
              className="w-40"
              aria-label="Period end"
            />
          </div>

          {unremittedWorklogs.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">
              No unpaid worklogs available.
            </div>
          ) : (
            <div className="overflow-auto max-h-96 space-y-4">
              {Array.from(new Set(unremittedWorklogs.map((wl) => wl.user_id))).map(
                (userId) => {
                  const userWls = unremittedWorklogs.filter(
                    (wl) => wl.user_id === userId,
                  )
                  const first = userWls[0]
                  const isUserExcluded = excludedUsers.has(userId as string)
                  const userTotal = userWls
                    .filter(
                      (wl) =>
                        !excludedIds.has(wl.id) && !excludedUsers.has(wl.user_id),
                    )
                    .reduce((sum: number, wl: any) => sum + wl.total_earnings, 0)

                  return (
                    <div key={userId as string} className="rounded-md border">
                      <div className="flex items-center gap-3 px-4 py-3 bg-muted/40 rounded-t-md">
                        <Checkbox
                          id={`user-${userId}`}
                          checked={!isUserExcluded}
                          onCheckedChange={() =>
                            toggleExcludeUser(userId as string)
                          }
                          aria-label={`Include all worklogs for ${first.freelancer_name ?? first.freelancer_email}`}
                        />
                        <label
                          htmlFor={`user-${userId}`}
                          className="flex-1 font-medium cursor-pointer"
                        >
                          {first.freelancer_name ?? first.freelancer_email}
                          <span className="ml-2 text-sm font-normal text-muted-foreground">
                            {first.freelancer_email}
                          </span>
                        </label>
                        <span className="font-mono text-sm font-semibold">
                          ${userTotal.toFixed(2)}
                        </span>
                      </div>
                      <div className="divide-y">
                        {userWls.map((wl: any) => {
                          const isWlExcluded = isUserExcluded || excludedIds.has(wl.id)
                          return (
                            <div
                              key={wl.id}
                              className={`flex items-center gap-3 px-6 py-2.5 ${isWlExcluded ? "opacity-40" : ""}`}
                            >
                              <Checkbox
                                id={`wl-${wl.id}`}
                                checked={!isWlExcluded}
                                disabled={isUserExcluded}
                                onCheckedChange={() => toggleExcludeWorklog(wl.id)}
                                aria-label={`Include worklog ${wl.task_name}`}
                              />
                              <label
                                htmlFor={`wl-${wl.id}`}
                                className="flex-1 text-sm cursor-pointer"
                              >
                                {wl.task_name}
                              </label>
                              <span className="font-mono text-sm">
                                ${wl.total_earnings.toFixed(2)}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  )
                },
              )}
            </div>
          )}

          <div className="flex items-center justify-between border-t pt-3">
            <p className="text-sm text-muted-foreground">
              {selectedForPayment.length} worklog
              {selectedForPayment.length !== 1 ? "s" : ""} across{" "}
              {Object.keys(byFreelancer).length} freelancer
              {Object.keys(byFreelancer).length !== 1 ? "s" : ""}
            </p>
            <p className="font-semibold">
              Total: $
              {selectedForPayment
                .reduce((s: number, wl: any) => s + wl.total_earnings, 0)
                .toFixed(2)}
            </p>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowPayment(false)}
              disabled={paymentLoading}
            >
              Cancel
            </Button>
            <Button
              onClick={confirmPayment}
              disabled={paymentLoading || selectedForPayment.length === 0}
            >
              {paymentLoading ? "Processing…" : "Confirm Payment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

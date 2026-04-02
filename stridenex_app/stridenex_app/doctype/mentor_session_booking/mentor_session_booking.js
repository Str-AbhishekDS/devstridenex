// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt
//
// REPLACE "your_app" below with your actual Frappe app name.
// ─────────────────────────────────────────────────────────────────────────────

const APP = "stridenex_app";   // ← change this

// ─────────────────────────────────────────────────────────────────────────────
// Slot Calendar Styles  (injected once into the page)
// ─────────────────────────────────────────────────────────────────────────────

function _inject_styles() {
    
    if (document.getElementById("msb-slot-styles")) return;

    const css = `
/* ── Slot Calendar Popup ─────────────────────────────────────────────── */
#msb-slot-overlay {
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(15, 17, 26, 0.72);
    backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
    animation: msb-fade-in 0.18s ease;
}
@keyframes msb-fade-in { from { opacity: 0 } to { opacity: 1 } }

#msb-slot-panel {
    background: #fff;
    border-radius: 16px;
    width: min(96vw, 860px);
    max-height: 88vh;
    display: flex; flex-direction: column;
    box-shadow: 0 32px 80px rgba(0,0,0,0.28);
    overflow: hidden;
    font-family: 'DM Sans', 'Segoe UI', sans-serif;
    animation: msb-slide-up 0.22s cubic-bezier(.22,.68,0,1.2);
}
@keyframes msb-slide-up {
    from { transform: translateY(32px); opacity: 0 }
    to   { transform: translateY(0);    opacity: 1 }
}

/* Header */
.msb-header {
    background: linear-gradient(135deg, #1e2a4a 0%, #2e3f6f 100%);
    color: #fff;
    padding: 20px 24px 16px;
    display: flex; align-items: flex-start; justify-content: space-between;
    flex-shrink: 0;
}
.msb-header h2 {
    margin: 0 0 4px;
    font-size: 18px; font-weight: 700; letter-spacing: -0.3px;
}
.msb-header p { margin: 0; font-size: 13px; opacity: .75; }
.msb-close-btn {
    background: rgba(255,255,255,0.15); border: none; cursor: pointer;
    color: #fff; border-radius: 8px; width: 32px; height: 32px;
    font-size: 18px; line-height: 1; display: flex; align-items: center;
    justify-content: center; transition: background .15s; flex-shrink: 0;
}
.msb-close-btn:hover { background: rgba(255,255,255,0.28); }

/* Week navigation */
.msb-week-nav {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 24px 10px;
    border-bottom: 1px solid #f0f0f4;
    flex-shrink: 0;
    background: #fafbfd;
}
.msb-week-label {
    flex: 1; text-align: center;
    font-size: 14px; font-weight: 600; color: #1e2a4a;
}
.msb-nav-btn {
    background: #fff; border: 1.5px solid #e3e7f0;
    border-radius: 8px; width: 34px; height: 34px; cursor: pointer;
    font-size: 16px; color: #4a5568; display: flex;
    align-items: center; justify-content: center;
    transition: all .15s;
}
.msb-nav-btn:hover { background: #1e2a4a; color: #fff; border-color: #1e2a4a; }
.msb-nav-btn:disabled { opacity: .35; cursor: not-allowed; }

/* Legend */
.msb-legend {
    display: flex; gap: 16px; align-items: center;
    padding: 8px 24px 10px;
    flex-shrink: 0; flex-wrap: wrap;
}
.msb-legend-item {
    display: flex; align-items: center; gap: 6px;
    font-size: 12px; color: #6b7280;
}
.msb-legend-dot {
    width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0;
}
.msb-legend-dot.available  { background: #22c55e; }
.msb-legend-dot.booked     { background: #f59e0b; }
.msb-legend-dot.blocked    { background: #ef4444; }

/* Day columns scroll area */
.msb-calendar-scroll {
    flex: 1; overflow-y: auto; overflow-x: auto;
    padding: 0 24px 20px;
}
.msb-days-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(96px, 1fr));
    gap: 10px;
    min-width: 640px;
    padding-top: 16px;
}

/* Day column */
.msb-day-col { display: flex; flex-direction: column; gap: 6px; }
.msb-day-header {
    text-align: center; padding: 6px 4px;
    border-radius: 8px; font-size: 11px; font-weight: 700;
    letter-spacing: .5px; text-transform: uppercase; color: #6b7280;
    margin-bottom: 2px;
}
.msb-day-header.today {
    background: #1e2a4a; color: #fff;
}
.msb-day-header span { display: block; font-size: 18px; font-weight: 800; margin-bottom: 1px; color: inherit; }
.msb-day-header.today span { color: #fff; }
.msb-day-empty {
    font-size: 11px; color: #c0c4cc; text-align: center;
    padding: 14px 0; font-style: italic;
}

/* Slot chips */
.msb-slot {
    border-radius: 8px; padding: 8px 8px 7px;
    font-size: 11.5px; line-height: 1.3;
    border: 1.5px solid transparent;
    transition: transform .12s, box-shadow .12s, opacity .12s;
    position: relative; overflow: hidden;
}
.msb-slot-time { font-weight: 700; display: block; font-size: 12px; }
.msb-slot-label { font-size: 10.5px; opacity: .75; display: block; margin-top: 1px; }

/* Available slot */
.msb-slot.available {
    background: #f0fdf4; border-color: #86efac;
    color: #166534; cursor: pointer;
}
.msb-slot.available:hover {
    background: #22c55e; color: #fff; border-color: #16a34a;
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(34,197,94,.28);
}
.msb-slot.available:hover .msb-slot-label { opacity: .9; }

/* Booked slot */
.msb-slot.booked {
    background: #fffbeb; border-color: #fcd34d;
    color: #92400e; cursor: default;
}
.msb-slot.booked::after {
    content: '';
    position: absolute; inset: 0;
    background: repeating-linear-gradient(
        -45deg, transparent, transparent 4px,
        rgba(245,158,11,.10) 4px, rgba(245,158,11,.10) 8px
    );
}

/* Blocked slot */
.msb-slot.blocked {
    background: #fef2f2; border-color: #fca5a5;
    color: #991b1b; cursor: not-allowed; opacity: .85;
}
.msb-slot.blocked::before {
    content: '🔒';
    position: absolute; right: 5px; top: 4px; font-size: 10px; opacity: .6;
}

/* Booking confirmation panel */
.msb-confirm-bar {
    background: #f0fdf4;
    border-top: 1.5px solid #86efac;
    padding: 14px 24px;
    display: flex; align-items: center; gap: 14px;
    flex-shrink: 0; flex-wrap: wrap;
}
.msb-confirm-bar.hidden { display: none; }
.msb-confirm-info { flex: 1; }
.msb-confirm-info strong { display: block; font-size: 13.5px; color: #166534; }
.msb-confirm-info span { font-size: 12px; color: #6b7280; }
.msb-topic-input {
    flex: 1; min-width: 180px;
    border: 1.5px solid #86efac; border-radius: 8px;
    padding: 8px 12px; font-size: 13px;
    outline: none; transition: border-color .15s;
}
.msb-topic-input:focus { border-color: #22c55e; }
.msb-confirm-btn {
    background: #22c55e; color: #fff;
    border: none; border-radius: 8px;
    padding: 9px 20px; font-size: 13px; font-weight: 700;
    cursor: pointer; transition: all .15s; white-space: nowrap;
}
.msb-confirm-btn:hover { background: #16a34a; transform: translateY(-1px); }
.msb-confirm-btn:disabled { background: #9ca3af; cursor: not-allowed; transform: none; }
.msb-cancel-sel {
    background: none; border: 1.5px solid #e3e7f0; border-radius: 8px;
    padding: 8px 14px; font-size: 13px; cursor: pointer; color: #6b7280;
    transition: all .15s;
}
.msb-cancel-sel:hover { background: #f3f4f6; }

/* Loading spinner */
.msb-loading {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 60px 0; gap: 14px;
    color: #6b7280; font-size: 14px;
}
.msb-spinner {
    width: 36px; height: 36px; border-radius: 50%;
    border: 3px solid #e3e7f0; border-top-color: #1e2a4a;
    animation: msb-spin .7s linear infinite;
}
@keyframes msb-spin { to { transform: rotate(360deg) } }

/* Tooltip */
.msb-tooltip {
    position: absolute; bottom: calc(100% + 6px); left: 50%;
    transform: translateX(-50%);
    background: #1e2a4a; color: #fff;
    font-size: 11px; padding: 5px 9px;
    border-radius: 6px; white-space: nowrap; pointer-events: none;
    z-index: 10; opacity: 0; transition: opacity .15s;
    max-width: 180px; white-space: normal; text-align: center;
}
.msb-slot:hover .msb-tooltip { opacity: 1; }
`;

    const el = document.createElement("style");
    el.id = "msb-slot-styles";
    el.textContent = css;
    document.head.appendChild(el);
}


// ─────────────────────────────────────────────────────────────────────────────
// Slot Calendar Class
// ─────────────────────────────────────────────────────────────────────────────

class SlotCalendar {
    constructor(opts) {
        // opts: { mentor, student, onBooked }
        this.isReschedule = opts.isReschedule || false;
        this.mentor = opts.mentor;
        this.student = opts.student;
        this.onBooked = opts.onBooked || (() => {});
        this.weekOffset = 0;            // 0 = current week
        this.calendarData = {};         // date → slots[]
        this.selectedSlot = null;       // { date, slot }
        this.$overlay = null;
    }

    // ── Public ──────────────────────────────────────────────────────

    open() {
        _inject_styles();
        this._buildOverlay();
        document.body.appendChild(this.$overlay);
        this._loadWeek();
    }

    close() {
        this.$overlay && this.$overlay.remove();
        this.$overlay = null;
    }

    // ── Private ─────────────────────────────────────────────────────

    _weekDates(offset) {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + 1 + offset * 7);
        const days = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(monday);
            d.setDate(monday.getDate() + i);
            days.push(d);
        }
        return days;
    }

    _fmt(date) {
        // Returns YYYY-MM-DD
        return date.toISOString().slice(0, 10);
    }

    _buildOverlay() {
        const div = document.createElement("div");
        div.id = "msb-slot-overlay";
        div.innerHTML = `
<div id="msb-slot-panel">
    <div class="msb-header">
        <div>
            <h2>📅 Book a Session</h2>
            <p>Select an available slot to book with <strong id="msb-mentor-name">${this.mentor}</strong></p>
        </div>
        <button class="msb-close-btn" id="msb-close-btn">✕</button>
    </div>

    <div class="msb-week-nav">
        <button class="msb-nav-btn" id="msb-prev-week" title="Previous week">‹</button>
        <div class="msb-week-label" id="msb-week-label">Loading…</div>
        <button class="msb-nav-btn" id="msb-next-week" title="Next week">›</button>
    </div>

    <div class="msb-legend">
        <div class="msb-legend-item"><div class="msb-legend-dot available"></div>Available – click to book</div>
        <div class="msb-legend-item"><div class="msb-legend-dot booked"></div>Already booked</div>
        <div class="msb-legend-item"><div class="msb-legend-dot blocked"></div>Blocked by mentor</div>
    </div>

    <div class="msb-calendar-scroll">
        <div class="msb-days-grid" id="msb-days-grid">
            <div class="msb-loading"><div class="msb-spinner"></div>Fetching availability…</div>
        </div>
    </div>

    <div class="msb-confirm-bar hidden" id="msb-confirm-bar">
        <div class="msb-confirm-info">
            <strong id="msb-sel-label">—</strong>
            <span>Click Confirm to book this slot</span>
        </div>
        <input class="msb-topic-input" id="msb-topic-input" placeholder="Session topic / notes…" />
        <button class="msb-cancel-sel" id="msb-cancel-sel">✕ Clear</button>
        <button class="msb-confirm-btn" id="msb-confirm-btn">✓ Confirm Booking</button>
    </div>
</div>`;

        this.$overlay = div;
        this._bindEvents();
    }

    _bindEvents() {
        const $ = (id) => this.$overlay.querySelector(`#${id}`);

        $("msb-close-btn").addEventListener("click", () => this.close());
        this.$overlay.addEventListener("click", (e) => {
            if (e.target === this.$overlay) this.close();
        });

        $("msb-prev-week").addEventListener("click", () => {
            // Don't go before current week
            if (this.weekOffset <= 0) return;
            this.weekOffset--;
            this._loadWeek();
        });

        $("msb-next-week").addEventListener("click", () => {
            this.weekOffset++;
            this._loadWeek();
        });

        $("msb-cancel-sel").addEventListener("click", () => this._clearSelection());

        $("msb-confirm-btn").addEventListener("click", () => this._confirmBooking());
    }

    _updateNavState() {
        const prev = this.$overlay.querySelector("#msb-prev-week");
        prev.disabled = this.weekOffset <= 0;
    }

    _loadWeek() {
        this._updateNavState();

        const days = this._weekDates(this.weekOffset);
        const from_date = this._fmt(days[0]);
        const to_date   = this._fmt(days[6]);

        // Update week label
        this.$overlay.querySelector("#msb-week-label").textContent =
            `${days[0].toLocaleDateString("en-IN", { day: "numeric", month: "short" })} – ` +
            `${days[6].toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;

        // Show spinner
        this.$overlay.querySelector("#msb-days-grid").innerHTML =
            `<div class="msb-loading"><div class="msb-spinner"></div>Fetching availability…</div>`;

        this._clearSelection();

        frappe.call({
            method: `${APP}.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.get_slot_calendar`,
            args: { mentor: this.mentor, from_date, to_date },
            callback: ({ message: data }) => {
                this.calendarData = data || {};
                this._renderGrid(days);
            },
            error: () => {
                this.$overlay.querySelector("#msb-days-grid").innerHTML =
                    `<div class="msb-loading" style="color:#ef4444">⚠ Failed to load slots. Check your app name and API.</div>`;
            },
        });
    }

    _renderGrid(days) {
        const todayStr = this._fmt(new Date());
        const grid = this.$overlay.querySelector("#msb-days-grid");
        grid.innerHTML = "";

        days.forEach((date) => {
            const dateStr = this._fmt(date);
            const isPast  = dateStr < todayStr;
            const isToday = dateStr === todayStr;
            const slots   = this.calendarData[dateStr] || [];

            const col = document.createElement("div");
            col.className = "msb-day-col";

            // Day header
            const hdr = document.createElement("div");
            hdr.className = "msb-day-header" + (isToday ? " today" : "");
            const dayName = date.toLocaleDateString("en-IN", { weekday: "short" });
            const dayNum  = date.getDate();
            hdr.innerHTML = `<span>${dayNum}</span>${dayName}`;
            col.appendChild(hdr);

            if (!slots.length) {
                const empty = document.createElement("div");
                empty.className = "msb-day-empty";
                empty.textContent = "No slots";
                col.appendChild(empty);
            } else {
                slots.forEach((slot) => {
                    // Skip past slots
                    const effectiveStatus = (isPast && slot.status === "available") ? "past" : slot.status;
                    col.appendChild(this._buildSlotChip(dateStr, slot, effectiveStatus));
                });
            }

            grid.appendChild(col);
        });
    }

    _buildSlotChip(dateStr, slot, effectiveStatus) {
        const chip = document.createElement("div");

        const now = new Date();
        const slotDateTime = new Date(dateStr + "T" + slot.from_time);

        let isPastTime = false;  // ✅ declare FIRST

        // If same day → check time
        if (dateStr === this._fmt(new Date())) {
            if (slotDateTime <= now) {
                isPastTime = true;
            }
        }

        // ✅ now safe to use
        const finalStatus = isPastTime ? "past" : effectiveStatus;
        const displayClass = finalStatus === "past" ? "booked" : finalStatus;

        chip.className = `msb-slot ${displayClass}`;
        chip.dataset.date = dateStr;
        chip.dataset.from = slot.from_time;
        chip.dataset.to   = slot.to_time;

        const fromFmt = slot.from_time.slice(0, 5);
        const toFmt   = slot.to_time.slice(0, 5);

        let label = "";
        let tooltip = "";

        if (finalStatus === "past") {
            label = "Past";
            tooltip = "Slot time has passed";
        } else if (effectiveStatus === "available" && !isPastTime){
            label = "Click to book";
            tooltip = `Available ${fromFmt}–${toFmt}`;
        } else if (slot.status === "booked") {
            label = slot.student ? slot.student.split("@")[0] : "Booked";
            tooltip = slot.topic ? `Topic: ${slot.topic}` : "Session booked";
        } else if (slot.status === "blocked") {
            label = "Blocked";
            tooltip = slot.reason ? `Reason: ${slot.reason}` : "Mentor unavailable";
        } else {
            label = "Past";
            tooltip = "Slot has passed";
        }

        chip.innerHTML = `
            <span class="msb-slot-time">${fromFmt}–${toFmt}</span>
            <span class="msb-slot-label">${label}</span>
            <div class="msb-tooltip">${tooltip}</div>
        `;

        if (effectiveStatus === "available" && !isPastTime) {
            chip.addEventListener("click", () => this._selectSlot(dateStr, slot, chip));
        }

        return chip;
    }

    _selectSlot(dateStr, slot, chipEl) {
        // De-highlight previous
        this.$overlay.querySelectorAll(".msb-slot.selected-slot").forEach((el) => {
            el.classList.remove("selected-slot");
            el.style.cssText = "";
        });

        // Highlight selected
        chipEl.style.background = "#1e2a4a";
        chipEl.style.color = "#fff";
        chipEl.style.borderColor = "#1e2a4a";
        chipEl.style.boxShadow = "0 6px 20px rgba(30,42,74,.35)";
        chipEl.classList.add("selected-slot");

        this.selectedSlot = { date: dateStr, slot };

        // Update confirm bar
        const date = new Date(dateStr + "T00:00:00");
        const formatted = date.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
        const fromFmt = slot.from_time.slice(0, 5);
        const toFmt   = slot.to_time.slice(0, 5);

        this.$overlay.querySelector("#msb-sel-label").textContent =
            `${formatted}  ·  ${fromFmt} – ${toFmt}`;

        const bar = this.$overlay.querySelector("#msb-confirm-bar");
        bar.classList.remove("hidden");
        this.$overlay.querySelector("#msb-topic-input").focus();
    }

    _clearSelection() {
        this.selectedSlot = null;
        this.$overlay.querySelectorAll(".msb-slot.selected-slot").forEach((el) => {
            el.classList.remove("selected-slot");
            el.style.cssText = "";
        });
        const bar = this.$overlay.querySelector("#msb-confirm-bar");
        bar.classList.add("hidden");
        this.$overlay.querySelector("#msb-topic-input").value = "";
    }

    _confirmBooking() {
        if (!this.selectedSlot) return;

        const input = this.$overlay.querySelector("#msb-topic-input");

        // Get values FIRST ✅
        const { date, slot } = this.selectedSlot;

        // 👉 Handle Reschedule (no topic needed)
        if (this.isReschedule) {
            this.onBooked(null, date, slot);
            return;
        }

        // 👉 Normal Booking Flow
        const topic = input ? input.value.trim() : "";

        if (!topic) {
            if (input) {
                input.style.borderColor = "#ef4444"; // red
                input.focus();
            }

            frappe.show_alert({
                message: __("Please enter a session topic."),
                indicator: "orange"
            });
            return;
        } else {
            input.style.borderColor = "#86efac"; // green reset
        }

        const btn = this.$overlay.querySelector("#msb-confirm-btn");
        btn.disabled = true;
        btn.textContent = "Booking…";

        frappe.call({
            method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.book_slot`,
            args: {
                mentor: this.mentor,
                student: this.student,
                session_date: date,
                from_time: slot.from_time,
                to_time: slot.to_time,
                topic,
            },
            callback: ({ message }) => {
                frappe.show_alert({
                    message: __("Session booked! ID: {0}", [message.session_name]),
                    indicator: "green",
                });
                this.onBooked(message.session_name, date, slot);
                this.close();
            },
            error: () => {
                btn.disabled = false;
                btn.textContent = "✓ Confirm Booking";
            },
        });
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// Frappe Form Controller
// ─────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on("Mentor Session Booking", {

    setup(frm) {
        frm.set_query("mentor", () => ({ }));
        frm.set_query("student", () => ({ }));
    },

    refresh(frm) {
        _inject_styles();
        _set_status_indicator(frm);
        _render_action_buttons(frm);
        _toggle_meeting_link(frm);
        
        // ── "Browse & Book Slots" button ──────────────────────────────
        if (frm.is_new() || frm.doc.status === "Scheduled") {
            frm.add_custom_button(__("📅 Browse & Book Slots"), () => {
                const mentor  = frm.doc.mentor;
                const student = frm.doc.student || frappe.session.user;

                if (!mentor) {
                    frappe.msgprint(__("Please select a Mentor first."));
                    return;
                }

                const cal = new SlotCalendar({
                    mentor,
                    student,
                    onBooked(sessionName, date, slot) {
                        // If this is a new form, pre-fill and reload
                        if (frm.is_new()) {
                            frm.set_value("session_date", date);
                            frm.set_value("from_time", slot.from_time);
                            frm.set_value("to_time", slot.to_time);
                            frappe.set_route("Form", "Mentor Session Booking", sessionName);
                        } else {
                            frm.reload_doc();
                        }
                    },
                });
                cal.open();
            });
        }
    },

    // ── Field Events ──────────────────────────────────────────────────

    mentor(frm) {
        frm.set_value("from_time", null);
        frm.set_value("to_time", null);

        if (frm.doc.mentor && frm.doc.session_date) {
            open_slot_calendar(frm);
        }
    },

    session_date(frm) {
        const today = frappe.datetime.get_today();

        if (frm.doc.session_date && frm.doc.session_date < today) {
            frappe.show_alert({
                message: __("Session date cannot be in the past."),
                indicator: "red"
            });
            frm.set_value("session_date", null);
            return;
        }

        if (frm.doc.mentor && frm.doc.session_date) {
            open_slot_calendar(frm);
        }
    },

    from_time(frm) { _validate_time_range(frm); _auto_duration(frm); },
    to_time(frm)   { _validate_time_range(frm); _auto_duration(frm); },
    status(frm)    { _set_status_indicator(frm); },
});


// ─────────────────────────────────────────────────────────────────────────────
// Private Helpers
// ─────────────────────────────────────────────────────────────────────────────

function _validate_time_range(frm) {
    const { from_time, to_time } = frm.doc;
    if (from_time && to_time && from_time >= to_time) {
        frappe.show_alert({ message: __("From Time must be earlier than To Time."), indicator: "red" });
    }
}

function _auto_duration(frm) {
    const { from_time, to_time } = frm.doc;
    if (!from_time || !to_time) return;
    const mins = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
    const diff = mins(to_time) - mins(from_time);
    if (diff > 0) frm.set_value("duration", diff);
}

function _set_status_indicator(frm) {
    const map = { Scheduled: "blue", Completed: "green", Cancelled: "red" };
    frm.page && frm.page.set_indicator(frm.doc.status, map[frm.doc.status] || "grey");
}

function _toggle_meeting_link(frm) {
    frm.set_df_property("meeting_link", "hidden", !frm.doc.meeting_link);
}

function _render_action_buttons(frm) {
    ["Reschedule", "Cancel Session", "Mark as Completed"].forEach((b) =>
        frm.remove_custom_button(__(b))
    );

    if (frm.is_new() || frm.doc.status !== "Scheduled") return;

    frm.add_custom_button(__("Reschedule"),        () => open_reschedule_calendar(frm), __("Actions"));
    frm.add_custom_button(__("Cancel Session"),    () => _cancel_session(frm),           __("Actions"));
    frm.add_custom_button(__("Mark as Completed"), () => _mark_completed(frm),           __("Actions"));
} 

function _open_reschedule_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Reschedule Session"),
        fields: [
            { label: __("New Date"),      fieldname: "new_date",      fieldtype: "Date", reqd: 1 },
            { label: __("New From Time"), fieldname: "new_from_time", fieldtype: "Time", reqd: 1 },
            { label: __("New To Time"),   fieldname: "new_to_time",   fieldtype: "Time", reqd: 1 },
        ],
        primary_action_label: __("Reschedule"),
        primary_action({ new_date, new_from_time, new_to_time }) {
            frappe.call({
                method: `${APP}.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.reschedule_session`,
                args: { session_name: frm.doc.name, new_date, new_from_time, new_to_time },
                callback({ message }) {
                    frappe.show_alert({ message, indicator: "green" });
                    frm.reload_doc();
                    d.hide();
                },
            });
        },
    });
    d.show();
}

function _cancel_session(frm) {
    frappe.confirm(__("Cancel session {0}?", [frm.doc.name]), () => {
        frappe.call({
            method: `${APP}.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.cancel_session`,
            args: { session_name: frm.doc.name },
            callback({ message }) {
                frappe.show_alert({ message, indicator: "green" });
                frm.reload_doc();
            },
        });
    });
}

function _mark_completed(frm) {
    frappe.confirm(__("Mark {0} as Completed?", [frm.doc.name]), () => {
        frappe.call({
            method: `${APP}.stridenex_app.doctype.mentor_session_booking.mentor_session_booking.mark_session_completed`,
            args: { session_name: frm.doc.name },
            callback({ message }) {
                frappe.show_alert({ message, indicator: "green" });
                frm.reload_doc();
            },
        });
    });
}

function open_slot_calendar(frm) {
    const mentor  = frm.doc.mentor;
    const student = frm.doc.student || frappe.session.user;

    if (!mentor) {
        frappe.msgprint(__("Please select a Mentor first."));
        return;
    }

    const cal = new SlotCalendar({
        mentor,
        student,
        onBooked(sessionName, date, slot) {
            if (frm.is_new()) {
                frm.set_value("session_date", date);
                frm.set_value("from_time", slot.from_time);
                frm.set_value("to_time", slot.to_time);

                frappe.set_route("Form", "Mentor Session Booking", sessionName);
            } else {
                frm.reload_doc();
            }
        },
    });

    cal.open();
}

function open_reschedule_calendar(frm) {
    const cal = new SlotCalendar({
        mentor: frm.doc.mentor,
        student: frm.doc.student,
        isReschedule: true, 

        onBooked(sessionName, date, slot) {
            // ✅ ONLY reschedule (NO new booking)
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.reschedule_session`,
                args: {
                    session_name: frm.doc.name,
                    new_date: date,
                    new_from_time: slot.from_time,
                    new_to_time: slot.to_time
                },
                callback: () => {
                    frappe.show_alert({
                        message: "Session Rescheduled",
                        indicator: "green"
                    });
                    frm.reload_doc();
                }
            });
        }
    });

    cal.open();
}

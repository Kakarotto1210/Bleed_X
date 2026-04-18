const API_BASE = (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") ? "http://localhost:8000" : "";
let selectedFile = null;
let categoryChartInstance = null;
let trendChartInstance = null;

// ---- Upload handling ----
const dropZone = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => {
    dropZone.classList.remove("drag-over");
});
dropZone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropZone.classList.remove("drag-over");
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

function handleFileSelect(e) {
    if (e.target.files.length) handleFile(e.target.files[0]);
}

function handleFile(file) {
    const ext = file.name.split(".").pop().toLowerCase();
    if (!["csv", "xlsx", "xls", "pdf"].includes(ext)) {
        alert("Please upload a PDF, CSV, or Excel file.");
        return;
    }
    selectedFile = file;
    document.getElementById("file-info").classList.remove("hidden");
    document.getElementById("file-name").textContent = file.name;
    document.getElementById("upload-icon").textContent = "✅";
    document.getElementById("upload-text").textContent = "File ready!";
    document.getElementById("analyze-btn").disabled = false;
}

function clearFile() {
    selectedFile = null;
    fileInput.value = "";
    document.getElementById("file-info").classList.add("hidden");
    document.getElementById("upload-icon").textContent = "📁";
    document.getElementById("upload-text").textContent = "Drag & Drop your CSV, Excel, or PDF here";
    document.getElementById("analyze-btn").disabled = true;
}

function scrollToUpload() {
    document.getElementById("upload-section").scrollIntoView({ behavior: "smooth" });
}

// ---- Analyze ----
async function analyzeFile() {
    if (!selectedFile) return;

    // Show loading
    document.getElementById("landing").style.display = "none";
    document.getElementById("loading-screen").style.display = "flex";

    // Animate progress
    const pb = document.getElementById("progress-bar");
    const pt = document.getElementById("progress-text");

    const steps = [
        { w: "15%", t: "Reading file..." },
        { w: "35%", t: "Cleaning data..." },
        { w: "55%", t: "Categorizing transactions..." },
        { w: "75%", t: "Detecting leak patterns..." },
        { w: "90%", t: "Calculating leak score..." },
    ];

    let stepIdx = 0;
    const stepInterval = setInterval(() => {
        if (stepIdx < steps.length) {
            pb.style.width = steps[stepIdx].w;
            pt.textContent = steps[stepIdx].t;
            stepIdx++;
        }
    }, 400);

    try {
        const formData = new FormData();
        formData.append("file", selectedFile);

        const res = await fetch(`${API_BASE}/analyze`, {
            method: "POST",
            body: formData,
        });
        const data = await res.json();

        clearInterval(stepInterval);
        pb.style.width = "100%";
        pt.textContent = "Analysis complete!";

        if (!data.success) {
            alert("Error: " + data.error);
            goBack();
            return;
        }

        // Delay then show dashboard
        setTimeout(() => {
            document.getElementById("loading-screen").style.display = "none";
            document.getElementById("dashboard").style.display = "block";
            renderDashboard(data);
        }, 800);

    } catch (err) {
        clearInterval(stepInterval);
        alert("Failed to connect to server. Make sure the backend is running on port 8000.\n\n" + err.message);
        goBack();
    }
}

function goBack() {
    document.getElementById("dashboard").style.display = "none";
    document.getElementById("loading-screen").style.display = "none";
    document.getElementById("landing").style.display = "block";
    clearFile();
    // Destroy charts
    if (categoryChartInstance) { categoryChartInstance.destroy(); categoryChartInstance = null; }
    if (trendChartInstance) { trendChartInstance.destroy(); trendChartInstance = null; }
}

// ---- Render Dashboard ----
function renderDashboard(data) {
    window.latestData = data;
    // == Leak Score Gauge ==
    const score = data.leak_score;
    const ring = document.getElementById("score-ring");
    const circumference = 2 * Math.PI * 85; // ~534
    const offset = circumference - (score / 100) * circumference;
    ring.setAttribute("stroke-dasharray", circumference);

    // Color based on score
    let scoreColor = "#00ff88";
    let label = "Healthy 💚";
    if (score > 30 && score <= 60) { scoreColor = "#fbbf24"; label = "Warning ⚠️"; }
    if (score > 60) { scoreColor = "#f43f5e"; label = "Critical 🔴"; }
    ring.setAttribute("stroke", scoreColor);

    // Glow on card
    const scoreCard = document.getElementById("score-card");
    if (score > 60) scoreCard.classList.add("glow-red", "animate-glow");
    else if (score > 30) scoreCard.style.boxShadow = "0 0 30px rgba(251,191,36,0.2)";
    else scoreCard.classList.add("glow-green");

    // Animate number
    animateNumber("score-value", 0, Math.round(score), 1500);
    setTimeout(() => {
        ring.setAttribute("stroke-dashoffset", offset);
    }, 100);
    document.getElementById("score-label").textContent = label;

    // == Core Spending Metrics ==
    animateNumber("total-spend", 0, Math.round(data.total_spend), 1200, "₹");
    document.getElementById("leak-amount").textContent = "₹" + data.leak_amount.toLocaleString("en-IN");
    
    // == Budget System Integration ==
    const bdgt = data.budget || 50000;
    animateNumber("budget-limit", 0, Math.round(bdgt), 1200, "₹");
    
    // Compute Capital Burn Velocity
    const maxBurnRatio = Math.min((data.total_spend / bdgt) * 100, 100).toFixed(1);
    const burnProg = document.getElementById("burn-progress");
    document.getElementById("burn-percentage").textContent = maxBurnRatio + "%";
    
    setTimeout(() => {
        burnProg.style.width = maxBurnRatio + "%";
        if (maxBurnRatio >= 90) {
            burnProg.classList.remove("from-neon-purple");
            burnProg.classList.replace("to-bleed-500", "bg-bleed-600");
            burnProg.classList.add("animate-pulse", "shadow-[0_0_20px_rgba(244,63,94,0.8)]");
        }
    }, 500);

      // == Render AI Tips ==
    const insightsEl = document.getElementById("quick-insights");
    insightsEl.innerHTML = "";
    data.insights.forEach((insight, idx) => {
        let borderColor = "border-gray-800/50 hover:border-gray-600";
        if (insight.icon === '🚨' || insight.icon === '⚠️') borderColor = "border-bleed-500/30 hover:border-bleed-500";
        if (insight.icon === '🛡️') borderColor = "border-neon-green/30 hover:border-neon-green";

        const div = document.createElement("div");
        div.className = `p-5 bg-dark-900/50 rounded-2xl border ${borderColor} transition-colors flex items-start gap-4 animate-slide-up hover:bg-dark-900 shadow-lg`;
        div.style.animationDelay = (0.3 + idx * 0.1) + "s";
        div.innerHTML = `
            <div class="text-3xl filter drop-shadow-md"> ${insight.icon} </div>
            <p class="text-gray-300 text-sm leading-relaxed">${insight.text}</p>
        `;
        insightsEl.appendChild(div);
    });

    // == Render Top Categories ==
    const categoryList = document.getElementById("bleed-categories");
    categoryList.innerHTML = "";
    data.top_categories.slice(0, 5).forEach((item, idx) => {
        const h = document.createElement("div");
        h.className = "animate-slide-up flex flex-col gap-2 p-3 rounded-xl border border-gray-800 bg-dark-900/30 hover:bg-dark-900 transition-colors";
        h.style.animationDelay = (0.2 + idx * 0.1) + "s";
        h.innerHTML = `
            <div class="flex justify-between text-sm">
                <span class="text-gray-300 font-medium">${item.category}</span>
                <span class="text-white font-bold">₹${item.amount.toLocaleString()}</span>
            </div>
            <div class="w-full h-1.5 bg-dark-700 rounded-full overflow-hidden">
                <div class="h-full bg-bleed-500 rounded-full" style="width: ${item.percentage}%"></div>
            </div>
            <div class="text-[10px] text-gray-500 text-right">${item.percentage}% • ${item.count} txns</div>
        `;
        categoryList.appendChild(h);
    });
    
    // == Render Active Subscription Hub ==
    renderSubscriptionHub(data);

    // == Category Bar Chart ==
    renderCategoryChart(data.category_spend);

    // == Monthly Trend ==
    renderTrendChart(data.monthly_trend);

    // == Leak Details ==
    const leakEl = document.getElementById("leak-details");
    leakEl.innerHTML = "";
    (data.leaks || []).forEach((leak) => {
        const d = document.createElement("div");
        d.className = "glass rounded-xl p-6 card-hover border border-bleed-500/10";
        d.innerHTML = `
                    <div class="text-3xl mb-3">${leak.icon}</div>
                    <h4 class="text-white font-bold mb-2">${leak.type}</h4>
                    <p class="text-gray-400 text-sm leading-relaxed mb-3">${leak.message}</p>
                    <div class="flex items-center gap-4 text-xs text-gray-500">
                        <span class="text-bleed-400 font-bold text-base">₹${leak.amount.toLocaleString("en-IN")}</span>
                        <span>${leak.count} transactions</span>
                    </div>
                `;
        leakEl.appendChild(d);
    });
    if (data.leaks.length === 0) {
        leakEl.innerHTML = '<p class="text-gray-500 text-sm col-span-full">No major leaks detected. Your finances look healthy! 🎉</p>';
    }

    // == Actions ==
    const actEl = document.getElementById("action-cards");
    actEl.innerHTML = "";
    (data.actions || []).forEach((act) => {
        const d = document.createElement("div");
        d.className = "glass rounded-xl p-6 card-hover border border-neon-green/10 hover:border-neon-green/30 transition-colors cursor-pointer group";
        d.setAttribute("onclick", `executeMitigationProtocol('${act.filter || 'All'}', '${act.title}')`);
        d.innerHTML = `
                    <div class="text-2xl mb-3">${act.icon}</div>
                    <h4 class="text-white font-bold mb-2">${act.title}</h4>
                    <p class="text-gray-400 text-sm leading-relaxed">${act.description}</p>
                `;
        actEl.appendChild(d);
    });

    // == Interactive Transactions ==
    if (data.transactions) {
        document.getElementById('necessary-spend').textContent = '₹' + Math.round(data.necessary_spend || 0).toLocaleString('en-IN');
        document.getElementById('unnecessary-spend').textContent = '₹' + Math.round(data.unnecessary_spend || 0).toLocaleString('en-IN');
        
        const tableBody = document.getElementById('transaction-table-body');
        if (tableBody) {
            tableBody.innerHTML = '';
            
            // Show last 50 transactions to not freeze DOM
            data.transactions.slice(0, 50).forEach(txn => {
                const tr = document.createElement('tr');
                tr.className = "hover:bg-white/5 transition-all duration-300";
                tr.setAttribute("data-category", txn.category || "Other");
                
                const dt = new Date(txn.date);
                const dtStr = isNaN(dt) ? "Unknown" : dt.toLocaleDateString();

                let badgeColor = "bg-gray-500/20 text-gray-400";
                if (txn.user_mark === "necessary") badgeColor = "bg-green-500/20 text-green-400 ring-1 ring-green-500/50";
                else if (txn.user_mark === "unnecessary") badgeColor = "bg-red-500/20 text-red-400 ring-1 ring-red-500/50";

                tr.innerHTML = `
                    <td class="px-4 py-3 whitespace-nowrap">${dtStr}</td>
                    <td class="px-4 py-3 font-medium text-gray-200 truncate max-w-xs" title="${txn.description}">${txn.description}</td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-1 rounded inline-flex text-xs font-semibold ${badgeColor}">
                            ${txn.category || "Other"}
                        </span>
                    </td>
                    <td class="px-4 py-3 font-semibold ${txn.type === 'credit' ? 'text-neon-green' : 'text-gray-300'}">
                        ₹${Math.round(txn.amount).toLocaleString('en-IN')}
                    </td>
                    <td class="px-4 py-3 text-right whitespace-nowrap">
                        <div class="flex justify-end gap-2">
                            <button onclick="markTxn('${txn.id}', 'necessary')" class="px-2 py-1 bg-green-500/10 hover:bg-green-500/20 text-green-400 text-xs rounded transition-colors" title="Mark Necessary">✔️</button>
                            <button onclick="markTxn('${txn.id}', 'unnecessary')" class="px-2 py-1 bg-red-500/10 hover:bg-red-500/20 text-red-500 text-xs rounded transition-colors" title="Mark Unnecessary">❌</button>
                        </div>
                    </td>
                `;
                tableBody.appendChild(tr);
            });
        }
    }
}

// ---- Mark Transaction Action ----
async function markTxn(id, status) {
    try {
        const res = await fetch(`${API_BASE}/mark-transaction`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id, status })
        });
        const responseData = await res.json();
        if (responseData.success) {
            renderDashboard(responseData);
        } else {
            alert("Error: " + responseData.error);
        }
    } catch (e) {
        console.error("Failed to mark transaction:", e);
    }
}

// ---- Charts ----
function renderCategoryChart(categorySpend) {
    const ctx = document.getElementById("categoryChart").getContext("2d");
    const labels = Object.keys(categorySpend);
    const values = Object.values(categorySpend);

    const colors = [
        "rgba(244, 63, 94, 0.8)",
        "rgba(192, 132, 252, 0.8)",
        "rgba(0, 212, 255, 0.8)",
        "rgba(251, 191, 36, 0.8)",
        "rgba(0, 255, 136, 0.8)",
        "rgba(251, 113, 133, 0.8)",
        "rgba(147, 197, 253, 0.8)",
    ];

    if (categoryChartInstance) categoryChartInstance.destroy();
    categoryChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels,
            datasets: [{
                data: values,
                backgroundColor: colors.slice(0, labels.length),
                borderRadius: 8,
                borderSkipped: false,
                maxBarThickness: 50,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    ticks: { color: "#6b7280", font: { size: 11 } },
                    grid: { display: false },
                    border: { display: false },
                },
                y: {
                    ticks: { color: "#4b5563", font: { size: 10 }, callback: v => "₹" + (v / 1000).toFixed(0) + "K" },
                    grid: { color: "rgba(255,255,255,0.03)" },
                    border: { display: false },
                },
            },
            animation: { duration: 1200, easing: "easeOutQuart" },
        },
    });
}

function renderTrendChart(monthlyTrend) {
    const ctx = document.getElementById("trendChart").getContext("2d");
    const labels = Object.keys(monthlyTrend);
    const values = Object.values(monthlyTrend);

    if (labels.length === 0) {
        ctx.font = "14px Inter";
        ctx.fillStyle = "#6b7280";
        ctx.textAlign = "center";
        ctx.fillText("No monthly data available", ctx.canvas.width / 2, ctx.canvas.height / 2);
        return;
    }

    if (trendChartInstance) trendChartInstance.destroy();
    trendChartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: "#f43f5e",
                backgroundColor: (context) => {
                    const gradient = context.chart.ctx.createLinearGradient(0, 0, 0, 250);
                    gradient.addColorStop(0, "rgba(244, 63, 94, 0.3)");
                    gradient.addColorStop(1, "rgba(244, 63, 94, 0)");
                    return gradient;
                },
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointBackgroundColor: "#f43f5e",
                pointBorderColor: "#020205",
                pointBorderWidth: 3,
                borderWidth: 2.5,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    ticks: { color: "#6b7280", font: { size: 11 } },
                    grid: { display: false },
                    border: { display: false },
                },
                y: {
                    ticks: { color: "#4b5563", font: { size: 10 }, callback: v => "₹" + (v / 1000).toFixed(0) + "K" },
                    grid: { color: "rgba(255,255,255,0.03)" },
                    border: { display: false },
                },
            },
            animation: { duration: 1500, easing: "easeOutQuart" },
        },
    });
}

// ---- Animate number counter ----
function animateNumber(elId, start, end, duration, prefix = "") {
    const el = document.getElementById(elId);
    const startTime = performance.now();
    function update(now) {
        const elapsed = now - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
        const current = Math.round(start + (end - start) * eased);
        el.textContent = prefix + current.toLocaleString("en-IN");
        if (progress < 1) requestAnimationFrame(update);
    }
    requestAnimationFrame(update);
}

// ==== BLEEDX SYSTEM EXTENSIONS ====

// 1. AI Mitigation Executer
window.executeMitigationProtocol = function(filter, title) {
    const tableBody = document.getElementById('transaction-table-body');
    if(!tableBody) return;
    
    const alertEl = document.createElement('div');
    alertEl.className = 'fixed top-4 right-4 bg-bleed-500/20 text-bleed-400 border border-bleed-500/50 px-6 py-4 rounded-xl shadow-[0_0_20px_rgba(244,63,94,0.3)] animate-slide-up z-[9999] font-mono whitespace-pre-line';
    alertEl.innerHTML = `<strong>SYSTEM OVERRIDE: ${title}</strong><br/>Isolating bleeding signatures...`;
    document.body.appendChild(alertEl);
    setTimeout(() => alertEl.remove(), 4000);

    tableBody.parentElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    const rows = tableBody.querySelectorAll('tr');
    rows.forEach(tr => {
        const cat = tr.getAttribute('data-category');
        tr.style.opacity = '1';
        tr.classList.remove('bg-bleed-600/30', 'ring-1', 'ring-bleed-500/50');
        tr.style.transform = 'scale(1)';
        
        let shouldHighlight = false;
        if(filter === 'All') {
            shouldHighlight = true;
        } else if(filter === 'Curfew') {
            if(cat === 'Food' || cat === 'Other' || cat === 'Shopping') shouldHighlight = true;
        } else {
            if(cat === filter) shouldHighlight = true;
        }
        
        if (shouldHighlight && filter !== 'All') {
            tr.classList.add('bg-bleed-600/30', 'ring-1', 'ring-bleed-500/50');
            tr.style.transform = 'scale(1.02)';
        } else if (filter !== 'All') {
            tr.style.opacity = '0.15';
        }
    });
};

// 2. Global Matrix Live Search
window.searchMatrix = function() {
    const input = document.getElementById('global-search').value.toLowerCase();
    const tableBody = document.getElementById('transaction-table-body');
    if (!tableBody) return;
    
    tableBody.querySelectorAll('tr').forEach(tr => {
        const textContext = tr.innerText.toLowerCase();
        if (textContext.includes(input)) {
            tr.style.display = '';
        } else {
            tr.style.display = 'none';
        }
    });
};

// 3. System Export Protocol
window.exportBleedReport = function() {
    const tableBody = document.getElementById('transaction-table-body');
    if (!tableBody) return;
    
    let csvContent = "data:text/csv;charset=utf-8,";
    csvContent += "Date,Description,Category,Amount\n"; 
    
    tableBody.querySelectorAll('tr').forEach(tr => {
        if(tr.style.display !== 'none') {
            const cols = tr.querySelectorAll('td');
            if(cols.length >= 4) {
                const dt = cols[0].innerText.trim();
                const desc = `"${cols[1].innerText.trim().replace(/"/g, '""')}"`;
                const cat = cols[2].innerText.trim();
                const amt = cols[3].innerText.trim().replace(/₹|,/g, '');
                
                csvContent += `${dt},${desc},${cat},${amt}\n`;
            }
        }
    });

    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "BleedX_Terminal_Export_" + new Date().toISOString().split('T')[0] + ".csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};

// 4. Set Budget Override
window.updateBudget = async function() {
    const override = prompt("Enter new maximum absolute capital burn limit (₹):");
    if(override && !isNaN(override)) {
        try {
            const res = await fetch(`${API_BASE}/set-budget`, {
                method: "POST",
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ budget: parseFloat(override) })
            });
            const d = await res.json();
            if(d.success && window.latestData) {
                window.latestData.budget = d.budget;
                renderDashboard(window.latestData);
            }
        } catch(e) {
            console.error(e);
        }
    }
};

// 5. Connect SMS Device
window.registerSMS = async function() {
    const phone = prompt("Enter mobile number to link with BleedX Terminal (e.g. +91XXXXXXXXXX):");
    if(!phone) return;
    
    try {
        const res = await fetch(`${API_BASE}/register-sms`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ phone: phone })
        });
        const d = await res.json();
        if(d.success) {
            document.getElementById('btn-link-device').style.display = 'none';
            document.getElementById('btn-fire-report').style.display = 'flex';
            alert("✅ Device Linked successfully. SMS Dispatcher activated on backend.");
        } else {
            alert("Error linking device: " + d.error);
        }
    } catch(e) {
        console.error(e);
        alert("Failed to connect to BleedX Gateway.");
    }
};

// 6. Manual SMS Dispatch Fire Override
window.fireSMSReport = async function() {
    try {
        const res = await fetch(`${API_BASE}/send-sms-report`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' }
        });
        const d = await res.json();
        if(d.success) {
            alert("🚨 Payload fired globally over SMS gateway.");
        } else {
            alert("Failed to push report: " + d.error);
        }
    } catch(e) {
        console.error(e);
    }
};

// ==== ACTIVE SUBSCRIPTION & TERMINATION ENGINE ====
function renderSubscriptionHub(data) {
    const container = document.getElementById("subscription-container");
    container.innerHTML = "";
    
    // Find the subscription leak object in leaks payload
    let subLeak = null;
    if(data.leaks) {
        subLeak = data.leaks.find(l => l.type === "Recurring / Subscriptions");
    }
    
    if(!subLeak || !subLeak.details || subLeak.details.length === 0) {
        container.innerHTML = `<div class="bg-dark-900 border border-gray-800 p-4 rounded-xl flex items-center gap-3 col-span-full">
            <span class="text-2xl">🛡️</span>
            <div><div class="text-white font-bold text-sm">NO CRITICAL EXPOSURES</div><div class="text-[10px] text-gray-500 font-mono">Zero recurrent outbounds established via analysis loop.</div></div>
        </div>`;
        return;
    }
    
    subLeak.details.forEach(sub => {
        const div = document.createElement("div");
        div.className = "bg-dark-900/80 border border-gray-800 p-5 rounded-xl hover:border-bleed-500/50 transition-colors flex flex-col justify-between h-full relative overflow-hidden group";
        
        let safeName = sub.description.substring(0, 15);
        let extCost = sub.amount * 12; // Yearly projection
        
        div.innerHTML = `
            <div class="absolute -right-4 -top-4 w-16 h-16 bg-bleed-500/10 rounded-full blur-xl group-hover:bg-bleed-500/20 transition-all"></div>
            <div>
                <div class="text-[10px] text-bleed-400 font-bold font-mono tracking-widest mb-1 shadow-[0_0_5px_rgba(244,63,94,0.3)]">AUTHORIZED</div>
                <h4 class="text-white font-bold truncate text-base mb-2 capitalize">${safeName}</h4>
            </div>
            
            <div class="mt-4 border-t border-gray-800 pt-3">
                <div class="flex items-end justify-between mb-3">
                    <span class="text-2xl font-black text-white">₹${sub.amount.toLocaleString()}</span>
                    <span class="text-xs text-gray-500 font-mono uppercase">Avg / MO</span>
                </div>
                
                <button onclick="terminateSubscription('${escape(sub.description)}')" class="w-full bg-bleed-600/20 hover:bg-bleed-500 text-bleed-400 hover:text-white border border-bleed-500/50 hover:border-bleed-500 py-2 rounded-lg text-xs font-bold uppercase tracking-wider transition-all duration-300">
                    Force Terminate
                </button>
            </div>
        `;
        
        container.appendChild(div);
    });
}

window.terminateSubscription = async function(subName) {
    const decName = unescape(subName);
    const confirmed = confirm(`SYSTEM OVERRIDE\n\nInitiating secure protocol to terminate recurring authorization for: [${decName.toUpperCase()}].\n\nAre you absolutely sure you want to logically drop this outbound vector?`);
    if(!confirmed) return;
    
    try {
        const res = await fetch(`${API_BASE}/terminate-sub`, {
            method: "POST",
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ description: decName })
        });
        const d = await res.json();
        
        if(d.success) {
            alert(`❌ AUTHORIZATION REVOKED\n\nSimulated connection formally closed outbound pipeline against [${decName}].\n\n₹${d.reclaimed.toLocaleString()} was successfully stripped from historical network waste metrics!`);
            window.latestData = d.analysis;
            renderDashboard(window.latestData);
        } else {
            alert("Error terminating execution: " + d.error);
        }
    } catch(e) {
        console.error(e);
        alert("Gateway termination error. Server unresponsive.");
    }
};
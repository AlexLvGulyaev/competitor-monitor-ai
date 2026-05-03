/**
 * Competitor Monitor - Frontend Application
 * Мониторинг конкурентов - MVP ассистент
 */

// === State ===
const state = {
    currentTab: 'text',
    selectedImage: null,
    isLoading: false,
    /**
     * @type {{
     *   title: string,
     *   kind: 'competitor'|'image',
     *   pdfExportKind: 'text'|'site'|'image',
     *   siteHost?: string,
     *   sourceText?: string,
     *   competitor?: object,
     *   image?: object
     * } | null}
     */
    pdfExport: null
};

// === DOM Elements ===
const elements = {
    // Navigation
    navButtons: document.querySelectorAll('.nav-btn'),
    tabContents: document.querySelectorAll('.tab-content'),
    
    // Text analysis
    competitorText: document.getElementById('competitor-text'),
    analyzeTextBtn: document.getElementById('analyze-text-btn'),
    
    // Image analysis
    uploadZone: document.getElementById('upload-zone'),
    imageInput: document.getElementById('image-input'),
    previewContainer: document.getElementById('preview-container'),
    imagePreview: document.getElementById('image-preview'),
    removeImageBtn: document.getElementById('remove-image'),
    analyzeImageBtn: document.getElementById('analyze-image-btn'),
    
    // Parse demo
    urlInput: document.getElementById('url-input'),
    parseBtn: document.getElementById('parse-btn'),
    parseFormWrapper: document.getElementById('parse-form-wrapper'),
    parseCompactBar: document.getElementById('parse-compact-bar'),
    parseCompactUrl: document.getElementById('parse-compact-url'),
    parseEditBtn: document.getElementById('parse-edit-btn'),
    
    // History
    historyList: document.getElementById('history-list'),
    clearHistoryBtn: document.getElementById('clear-history-btn'),
    
    // Results
    resultsSection: document.getElementById('results-section'),
    resultsContent: document.getElementById('results-content'),
    closeResultsBtn: document.getElementById('close-results'),
    
    resultsLoading: document.getElementById('results-loading'),
    
    exitAppBtn: document.getElementById('exit-app-btn'),
    exportPdfBtn: document.getElementById('export-pdf-btn')
};

/**
 * Вкладки списков анализа (сильные / слабые / УТП / рекомендации) внутри #results-content
 */
/** Сегмент хоста для analysis_site_<host>.pdf (как на бэкенде). */
function sanitizeHostForFilename(host) {
    let h = String(host || '').trim().toLowerCase();
    if (h.startsWith('www.')) h = h.slice(4);
    h = h
        .replace(/[^a-z0-9._-]+/gi, '_')
        .replace(/_+/g, '_')
        .replace(/^[._-]+|[._-]+$/g, '')
        .slice(0, 48);
    return h;
}

function suggestedPdfDownloadName(p) {
    const k =
        p.pdfExportKind ?? (p.kind === 'image' ? 'image' : p.siteHost ? 'site' : 'text');
    if (k === 'image') return 'analysis_image.pdf';
    if (k === 'text') return 'analysis_text.pdf';
    const seg = sanitizeHostForFilename(p.siteHost || '');
    return seg ? `analysis_site_${seg}.pdf` : 'analysis_report.pdf';
}

function hostnameFromUrl(url) {
    try {
        const h = new URL(url).hostname.replace(/^www\./, '');
        return h || 'site';
    } catch {
        return 'site';
    }
}

function initResultTabs(root) {
    const wrap = root.querySelector('[data-analysis-tabs]');
    if (!wrap) return;

    const activate = (tabId) => {
        wrap.querySelectorAll('.analysis-tab-btn').forEach((btn) => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        wrap.querySelectorAll('.analysis-tab-panel').forEach((panel) => {
            panel.classList.toggle('active', panel.dataset.panel === tabId);
        });
    };

    wrap.querySelectorAll('.analysis-tab-btn').forEach((btn) => {
        btn.addEventListener('click', () => activate(btn.dataset.tab));
    });
}

// === API Functions ===
const api = {
    baseUrl: '',
    
    async analyzeText(text) {
        const response = await fetch(`${this.baseUrl}/analyze_text`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        return response.json();
    },
    
    async analyzeImage(file) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch(`${this.baseUrl}/analyze_image`, {
            method: 'POST',
            body: formData
        });
        return response.json();
    },
    
    async parseDemo(url) {
        const response = await fetch(`${this.baseUrl}/parse_demo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url })
        });
        return response.json();
    },
    
    async getHistory() {
        const response = await fetch(`${this.baseUrl}/history`);
        return response.json();
    },
    
    async clearHistory() {
        const response = await fetch(`${this.baseUrl}/history`, {
            method: 'DELETE'
        });
        return response.json();
    },
    
    async exportPdf(payload) {
        const response = await fetch(`${this.baseUrl}/export_pdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (!response.ok) {
            const errText = await response.text().catch(() => '');
            throw new Error(errText || `PDF: ${response.status}`);
        }
        return response.blob();
    }
};

// === UI Functions ===
const ui = {
    showLoading() {
        state.isLoading = true;
        elements.resultsSection.hidden = false;
        if (elements.resultsLoading) elements.resultsLoading.hidden = false;
        if (elements.resultsContent) elements.resultsContent.hidden = true;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
    },
    
    hideLoading() {
        state.isLoading = false;
        if (elements.resultsLoading) elements.resultsLoading.hidden = true;
        if (elements.resultsContent) elements.resultsContent.hidden = false;
    },
    
    showTab(tabId) {
        state.currentTab = tabId;
        
        // Update navigation
        elements.navButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        
        // Update content
        elements.tabContents.forEach(content => {
            content.classList.toggle('active', content.id === `${tabId}-tab`);
        });
        
        // Load history if needed
        if (tabId === 'history') {
            this.loadHistory();
        }
    },

    collapseParseForm(displayUrl) {
        if (elements.parseCompactUrl) {
            elements.parseCompactUrl.textContent = displayUrl;
            elements.parseCompactUrl.title = displayUrl;
        }
        if (elements.parseFormWrapper) elements.parseFormWrapper.hidden = true;
        if (elements.parseCompactBar) elements.parseCompactBar.hidden = false;
    },

    expandParseForm() {
        if (elements.parseFormWrapper) elements.parseFormWrapper.hidden = false;
        if (elements.parseCompactBar) elements.parseCompactBar.hidden = true;
        if (elements.urlInput) elements.urlInput.focus();
    },
    
    showResults(html) {
        if (elements.resultsLoading) elements.resultsLoading.hidden = true;
        if (elements.resultsContent) elements.resultsContent.hidden = false;
        elements.resultsContent.innerHTML = html;
        initResultTabs(elements.resultsContent);
        elements.resultsSection.hidden = false;
        elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
        this.syncPdfExportButton();
    },
    
    hideResults() {
        state.pdfExport = null;
        this.syncPdfExportButton();
        elements.resultsSection.hidden = true;
        if (elements.resultsLoading) elements.resultsLoading.hidden = true;
        if (elements.resultsContent) elements.resultsContent.hidden = false;
    },
    
    syncPdfExportButton() {
        const btn = elements.exportPdfBtn;
        if (!btn) return;
        const ok = !!state.pdfExport;
        btn.hidden = !ok;
        btn.disabled = !ok;
    },
    
    prepareExitSession() {
        if (state.isLoading) {
            state.isLoading = false;
            if (elements.resultsLoading) elements.resultsLoading.hidden = true;
            if (elements.resultsContent) elements.resultsContent.hidden = false;
        }
        this.hideResults();
        this.showTab('text');
    },
    
    showError(message) {
        state.pdfExport = null;
        this.syncPdfExportButton();
        const html = `
            <div class="error-message">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="12" r="10"/>
                    <line x1="12" y1="8" x2="12" y2="12"/>
                    <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>${message}</span>
            </div>
        `;
        this.showResults(html);
    },
    
    renderTextAnalysis(analysis) {
        const ds = analysis.design_score ?? 0;
        const ux = analysis.ux_score ?? 0;
        const hr = analysis.hr_relevance_score ?? 0;

        const scoreCard = (label, value, cls = '') => `
            <div class="analysis-score-card ${cls}">
                <div class="analysis-score-card__label">${label}</div>
                <div class="analysis-score-card__row">
                    <span class="analysis-score-card__value">${value}/10</span>
                    <div class="score-bar analysis-score-card__bar">
                        <div class="score-fill" style="width: ${(value / 10) * 100}%"></div>
                    </div>
                </div>
            </div>
        `;

        const scoresSection = `
            <div class="result-block result-block--scores">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="20" x2="18" y2="10"/>
                        <line x1="12" y1="20" x2="12" y2="4"/>
                        <line x1="6" y1="20" x2="6" y2="14"/>
                    </svg>
                    Оценки (HR / карьера / EdTech)
                </h3>
                <div class="analysis-scores-grid">
                    ${scoreCard('Дизайн и подача', ds)}
                    ${scoreCard('UX (работодатель / кандидат)', ux)}
                    ${scoreCard('Релевантность HR / найму', hr, 'analysis-score-card--full')}
                </div>
            </div>
        `;

        const audienceSection = analysis.target_audience ? `
            <div class="result-block result-block--compact">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                        <circle cx="9" cy="7" r="4"/>
                        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                        <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
                    </svg>
                    Целевая аудитория
                </h3>
                <p>${analysis.target_audience}</p>
            </div>
        ` : '';

        const tabSections = [
            { key: 'strengths', label: 'Сильные стороны', items: analysis.strengths },
            { key: 'weaknesses', label: 'Слабые стороны', items: analysis.weaknesses },
            { key: 'unique', label: 'Уникальные предложения', items: analysis.unique_offers },
            { key: 'recommendations', label: 'Рекомендации', items: analysis.recommendations }
        ].filter((s) => s.items && s.items.length > 0);

        let listsTabsSection = '';
        if (tabSections.length > 0) {
            const nav = tabSections.map((s, i) =>
                `<button type="button" class="analysis-tab-btn${i === 0 ? ' active' : ''}" data-tab="${s.key}">${s.label}</button>`
            ).join('');

            const panels = tabSections.map((s, i) => `
                <div class="analysis-tab-panel${i === 0 ? ' active' : ''}" data-panel="${s.key}">
                    <ul>
                        ${s.items.map((item) => `<li>${item}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

            listsTabsSection = `
                <div class="result-block result-block--tabs" data-analysis-tabs>
                    <h3 class="analysis-tabs-heading">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                            <line x1="16" y1="13" x2="8" y2="13"/>
                            <line x1="16" y1="17" x2="8" y2="17"/>
                        </svg>
                        Детали анализа
                    </h3>
                    <div class="analysis-tabs-nav" role="tablist">${nav}</div>
                    <div class="analysis-tabs-panels">${panels}</div>
                </div>
            `;
        }

        return `
            ${scoresSection}
            ${audienceSection}
            ${this.renderResultBlock('Автоматизация процессов', analysis.automation_potential || [], 'automation', true)}
            ${listsTabsSection}
            ${analysis.summary ? `
                <div class="result-block result-summary result-block--compact">
                    <h3>
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                            <polyline points="14 2 14 8 20 8"/>
                        </svg>
                        Резюме
                    </h3>
                    <p>${analysis.summary}</p>
                </div>
            ` : ''}
        `;
    },
    
    renderImageAnalysis(analysis) {
        const scorePercent = (analysis.visual_style_score / 10) * 100;
        
        return `
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
                        <circle cx="8.5" cy="8.5" r="1.5"/>
                        <polyline points="21 15 16 10 5 21"/>
                    </svg>
                    Описание изображения
                </h3>
                <p>${analysis.description}</p>
            </div>
            
            <div class="result-block">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
                    </svg>
                    Оценка визуального стиля
                </h3>
                <div class="score-display">
                    <span class="score-value">${analysis.visual_style_score}/10</span>
                    <div class="score-bar">
                        <div class="score-fill" style="width: ${scorePercent}%"></div>
                    </div>
                </div>
                <p>${analysis.visual_style_analysis}</p>
            </div>
            
            ${this.renderResultBlock('Маркетинговые инсайты', analysis.marketing_insights, 'insights')}
            ${this.renderResultBlock('Рекомендации', analysis.recommendations, 'recommendations')}
        `;
    },
    
    renderParsedContent(data) {
        const parsed = data;
        const analysisHtml = parsed.analysis ? this.renderTextAnalysis(parsed.analysis) : '';

        const technicalHtml = `
            <details class="parse-meta-details">
                <summary class="parse-meta-summary">Технические данные страницы</summary>
                <div class="parsed-content parse-meta-inner">
                    <div class="label">URL:</div>
                    <div class="value">${parsed.url}</div>
                    <div class="label">Title:</div>
                    <div class="value">${parsed.title || 'Не найден'}</div>
                    <div class="label">H1:</div>
                    <div class="value">${parsed.h1 || 'Не найден'}</div>
                    <div class="label">Первый абзац:</div>
                    <div class="value">${parsed.first_paragraph || 'Не найден'}</div>
                </div>
            </details>
        `;

        return `${analysisHtml}${technicalHtml}`;
    },
    
    renderResultBlock(title, items, type, compact = false) {
        if (!items || items.length === 0) return '';
        
        const icons = {
            strengths: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
            weaknesses: '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>',
            unique: '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
            recommendations: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/>',
            insights: '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>',
            automation: '<path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/><circle cx="12" cy="12" r="3"/>'
        };

        const blockClass = compact ? 'result-block result-block--compact' : 'result-block';
        
        return `
            <div class="${blockClass}">
                <h3>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        ${icons[type] || icons.recommendations}
                    </svg>
                    ${title}
                </h3>
                <ul>
                    ${items.map(item => `<li>${item}</li>`).join('')}
                </ul>
            </div>
        `;
    },
    
    async loadHistory() {
        try {
            const data = await api.getHistory();
            this.renderHistory(data.items);
        } catch (error) {
            console.error('Failed to load history:', error);
        }
    },
    
    renderHistory(items) {
        if (!items || items.length === 0) {
            elements.historyList.innerHTML = `
                <div class="history-empty">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="10"/>
                        <polyline points="12 6 12 12 16 14"/>
                    </svg>
                    <p>История пуста</p>
                </div>
            `;
            return;
        }
        
        const icons = {
            text: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
            image: '<rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/>',
            parse: '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>'
        };
        
        const typeLabels = {
            text: 'Анализ текста',
            image: 'Анализ изображения',
            parse: 'Парсинг сайта'
        };
        
        elements.historyList.innerHTML = items.map(item => {
            const date = new Date(item.timestamp);
            const timeStr = date.toLocaleString('ru-RU', {
                day: '2-digit',
                month: '2-digit',
                hour: '2-digit',
                minute: '2-digit'
            });
            
            return `
                <div class="history-item">
                    <div class="history-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            ${icons[item.request_type] || icons.text}
                        </svg>
                    </div>
                    <div class="history-content">
                        <div class="history-type">${typeLabels[item.request_type] || item.request_type}</div>
                        <div class="history-summary">${item.request_summary}</div>
                    </div>
                    <div class="history-time">${timeStr}</div>
                </div>
            `;
        }).join('');
    }
};

// === Event Handlers ===
const handlers = {
    // Navigation
    handleNavClick(e) {
        const btn = e.target.closest('.nav-btn');
        if (btn) {
            ui.showTab(btn.dataset.tab);
        }
    },
    
    // Text analysis
    async handleAnalyzeText() {
        const text = elements.competitorText.value.trim();
        
        if (text.length < 10) {
            ui.showError('Введите текст минимум 10 символов для анализа');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeText(text);
            
            if (result.success && result.analysis) {
                state.pdfExport = {
                    title: 'Анализ текста',
                    kind: 'competitor',
                    pdfExportKind: 'text',
                    sourceText: text,
                    competitor: result.analysis
                };
                ui.showResults(ui.renderTextAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // Image upload
    handleUploadClick() {
        elements.imageInput.click();
    },
    
    handleImageSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.processImage(file);
        }
    },
    
    handleDragOver(e) {
        e.preventDefault();
        elements.uploadZone.classList.add('dragover');
    },
    
    handleDragLeave(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
    },
    
    handleDrop(e) {
        e.preventDefault();
        elements.uploadZone.classList.remove('dragover');
        
        const file = e.dataTransfer.files[0];
        if (file && file.type.startsWith('image/')) {
            this.processImage(file);
        }
    },
    
    processImage(file) {
        state.selectedImage = file;
        
        const reader = new FileReader();
        reader.onload = (e) => {
            elements.imagePreview.src = e.target.result;
            elements.previewContainer.hidden = false;
            elements.uploadZone.querySelector('.upload-content').hidden = true;
            elements.analyzeImageBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    },
    
    handleRemoveImage() {
        state.selectedImage = null;
        elements.imageInput.value = '';
        elements.imagePreview.src = '';
        elements.previewContainer.hidden = true;
        elements.uploadZone.querySelector('.upload-content').hidden = false;
        elements.analyzeImageBtn.disabled = true;
    },
    
    async handleAnalyzeImage() {
        if (!state.selectedImage) {
            ui.showError('Выберите изображение для анализа');
            return;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.analyzeImage(state.selectedImage);
            
            if (result.success && result.analysis) {
                state.pdfExport = {
                    title: 'Анализ изображения',
                    kind: 'image',
                    pdfExportKind: 'image',
                    image: result.analysis
                };
                ui.showResults(ui.renderImageAnalysis(result.analysis));
            } else {
                ui.showError(result.error || 'Произошла ошибка при анализе изображения');
            }
        } catch (error) {
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // Parse demo
    async handleParse() {
        let url = elements.urlInput.value.trim();
        
        if (!url) {
            ui.showError('Введите URL сайта для парсинга');
            return;
        }
        
        // Add protocol if missing
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
        }
        
        ui.showLoading();
        
        try {
            const result = await api.parseDemo(url);
            
            if (result.success && result.data) {
                const displayUrl = result.data.url || url;
                const host = hostnameFromUrl(displayUrl);
                if (result.data.analysis) {
                    state.pdfExport = {
                        title: `Анализ сайта: ${host}`,
                        kind: 'competitor',
                        pdfExportKind: 'site',
                        siteHost: host,
                        competitor: result.data.analysis
                    };
                } else {
                    state.pdfExport = null;
                }
                ui.collapseParseForm(displayUrl);
                ui.showResults(ui.renderParsedContent(result.data));
            } else {
                ui.expandParseForm();
                ui.showError(result.error || 'Не удалось распарсить сайт');
            }
        } catch (error) {
            ui.expandParseForm();
            ui.showError('Ошибка соединения с сервером');
            console.error(error);
        } finally {
            ui.hideLoading();
        }
    },
    
    // History
    async handleClearHistory() {
        if (!confirm('Вы уверены, что хотите очистить историю?')) {
            return;
        }
        
        try {
            await api.clearHistory();
            ui.renderHistory([]);
        } catch (error) {
            console.error('Failed to clear history:', error);
        }
    },
    
    // Results
    handleCloseResults() {
        ui.hideResults();
    },
    
    async handleExportPdf() {
        const p = state.pdfExport;
        if (!p) return;
        const exportKind =
            p.pdfExportKind ??
            (p.kind === 'image' ? 'image' : p.siteHost ? 'site' : 'text');

        const body =
            p.kind === 'competitor'
                ? (() => {
                      const o = {
                          title: p.title,
                          kind: 'competitor',
                          competitor: p.competitor,
                          pdf_export_kind: exportKind
                      };
                      if (exportKind === 'site') {
                          o.site_host = p.siteHost || null;
                      }
                      if (exportKind === 'text' && p.sourceText != null && p.sourceText !== '') {
                          o.source_text = p.sourceText;
                      }
                      return o;
                  })()
                : {
                      title: p.title,
                      kind: 'image',
                      image: p.image,
                      pdf_export_kind: 'image'
                  };
        try {
            const blob = await api.exportPdf(body);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = suggestedPdfDownloadName(p);
            a.rel = 'noopener';
            document.body.appendChild(a);
            a.click();
            a.remove();
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error(e);
            alert('Не удалось сформировать PDF. Проверьте соединение с сервером.');
        }
    },
    
    handleExitApp() {
        handleExitClick();
    }
};

function initDesktopBridge() {
    if (typeof qt === 'undefined' || typeof qt.webChannelTransport === 'undefined') {
        return;
    }
    if (typeof QWebChannel === 'undefined') {
        return;
    }
    try {
        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.__desktopBridge = channel.objects.desktopBridge;
        });
    } catch (e) {
        console.warn('QWebChannel:', e);
    }
}

function showExitMessageForEnvironment() {
    if (/CompetitorMonitorDesktop/i.test(navigator.userAgent)) {
        alert('Приложение можно закрыть кнопкой окна');
    } else {
        alert('Закройте вкладку браузера для завершения работы');
    }
}

function handleExitClick() {
    ui.prepareExitSession();

    if (window.__desktopBridge && typeof window.__desktopBridge.requestExit === 'function') {
        try {
            window.__desktopBridge.requestExit();
        } catch (e) {
            showExitMessageForEnvironment();
        }
        return;
    }

    showExitMessageForEnvironment();
}

// === Initialize ===
function init() {
    // Navigation
    elements.navButtons.forEach(btn => {
        btn.addEventListener('click', handlers.handleNavClick.bind(handlers));
    });
    
    // Text analysis
    elements.analyzeTextBtn.addEventListener('click', handlers.handleAnalyzeText.bind(handlers));
    
    // Image upload
    elements.uploadZone.addEventListener('click', handlers.handleUploadClick.bind(handlers));
    elements.imageInput.addEventListener('change', handlers.handleImageSelect.bind(handlers));
    elements.uploadZone.addEventListener('dragover', handlers.handleDragOver.bind(handlers));
    elements.uploadZone.addEventListener('dragleave', handlers.handleDragLeave.bind(handlers));
    elements.uploadZone.addEventListener('drop', handlers.handleDrop.bind(handlers));
    elements.removeImageBtn.addEventListener('click', handlers.handleRemoveImage.bind(handlers));
    elements.analyzeImageBtn.addEventListener('click', handlers.handleAnalyzeImage.bind(handlers));
    
    // Parse demo
    elements.parseBtn.addEventListener('click', handlers.handleParse.bind(handlers));
    elements.urlInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handlers.handleParse.call(handlers);
    });
    if (elements.parseEditBtn) {
        elements.parseEditBtn.addEventListener('click', () => ui.expandParseForm());
    }
    
    // History
    elements.clearHistoryBtn.addEventListener('click', handlers.handleClearHistory.bind(handlers));
    
    // Results
    elements.closeResultsBtn.addEventListener('click', handlers.handleCloseResults.bind(handlers));
    if (elements.exportPdfBtn) {
        elements.exportPdfBtn.addEventListener('click', handlers.handleExportPdf.bind(handlers));
    }
    
    if (elements.exitAppBtn) {
        elements.exitAppBtn.addEventListener('click', handlers.handleExitApp.bind(handlers));
    }
    
    // Show default tab
    ui.showTab('text');
    
    initDesktopBridge();
}

// Start app
document.addEventListener('DOMContentLoaded', init);


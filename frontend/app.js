document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('job-form');
    const cvUpload = document.getElementById('cv-upload');
    const fileDropArea = document.querySelector('.file-drop-area');
    const fileMsg = document.querySelector('.file-msg');
    const modeRadios = document.querySelectorAll('input[name="analysis-mode"]');
    const singleJobGroup = document.getElementById('single-job-group');
    const bulkJobsGroup = document.getElementById('bulk-jobs-group');
    const formTitle = document.getElementById('form-section-title');
    const submitBtnText = document.getElementById('submit-btn-text');
    const onlyGoodFits = document.getElementById('only-good-fits');
    let lastBulkResults = null;

    function getMode() {
        const checked = document.querySelector('input[name="analysis-mode"]:checked');
        return checked ? checked.value : 'single';
    }

    function syncModeUI() {
        const bulk = getMode() === 'bulk';
        singleJobGroup.classList.toggle('hidden', bulk);
        bulkJobsGroup.classList.toggle('hidden', !bulk);
        formTitle.textContent = bulk
            ? 'Filter job postings with your CV'
            : 'Analyze a job';
        submitBtnText.textContent = bulk
            ? 'Score all postings & show best fits'
            : 'Compute fit & generate';
    }

    modeRadios.forEach((r) => r.addEventListener('change', syncModeUI));
    syncModeUI();

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach((eventName) => {
        fileDropArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ['dragenter', 'dragover'].forEach((eventName) => {
        fileDropArea.addEventListener(eventName, () => {
            fileDropArea.classList.add('drag-over');
        });
    });

    ['dragleave', 'drop'].forEach((eventName) => {
        fileDropArea.addEventListener(eventName, () => {
            fileDropArea.classList.remove('drag-over');
        });
    });

    cvUpload.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            fileMsg.textContent = e.target.files[0].name;
            fileDropArea.style.borderColor = 'var(--accent)';
        } else {
            fileMsg.textContent = 'Drag & Drop or Click to Select PDF';
            fileDropArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        }
    });

    onlyGoodFits.addEventListener('change', () => {
        if (lastBulkResults) {
            renderBulkResults(lastBulkResults);
        }
    });

    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const file = cvUpload.files[0];
        const apiKey = document.getElementById('api-key').value;
        const mode = getMode();

        if (!file || !file.name.endsWith('.pdf')) {
            showError('Please upload a valid PDF CV.');
            return;
        }

        if (mode === 'single') {
            const jobDesc = document.getElementById('job-desc').value;
            if (!jobDesc.trim()) {
                showError('Please paste a job description.');
                return;
            }
            const formData = new FormData();
            formData.append('cv_file', file);
            formData.append('job_description', jobDesc);
            if (apiKey.trim()) {
                formData.append('api_key', apiKey.trim());
            }

            setLoading(true);
            hideError();
            hideResults();

            try {
                const response = await fetch('/api/analyze', {
                    method: 'POST',
                    body: formData,
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.detail || 'Failed to analyze. Please try again.');
                }

                const data = await response.json();
                displayResults(data);
            } catch (error) {
                showError(error.message);
            } finally {
                setLoading(false);
            }
            return;
        }

        const bulkText = document.getElementById('jobs-bulk').value;
        if (!bulkText.trim()) {
            showError('Paste at least one job posting. Use ---NEXT JOB--- between different posts.');
            return;
        }

        const formData = new FormData();
        formData.append('cv_file', file);
        formData.append('jobs_bulk', bulkText);
        if (apiKey.trim()) {
            formData.append('api_key', apiKey.trim());
        }

        setLoading(true);
        hideError();
        hideResults();

        try {
            const response = await fetch('/api/filter-jobs', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || 'Failed to filter jobs. Please try again.');
            }

            const data = await response.json();
            lastBulkResults = data;
            displayBulkResults(data);
        } catch (error) {
            showError(error.message);
        } finally {
            setLoading(false);
        }
    });

    function setLoading(isLoading) {
        const btnText = document.querySelector('.btn-text');
        const loader = document.querySelector('.loader');
        const btn = document.getElementById('analyze-btn');

        if (isLoading) {
            btnText.classList.add('hidden');
            loader.classList.remove('hidden');
            btn.style.opacity = '0.8';
            btn.disabled = true;
        } else {
            btnText.classList.remove('hidden');
            loader.classList.add('hidden');
            btn.style.opacity = '1';
            btn.disabled = false;
        }
    }

    function showError(msg) {
        const errDiv = document.getElementById('error-message');
        errDiv.textContent = msg;
        errDiv.classList.remove('hidden');
    }

    function hideError() {
        document.getElementById('error-message').classList.add('hidden');
    }

    function hideResults() {
        document.getElementById('results-section').classList.add('hidden');
        document.getElementById('bulk-results-section').classList.add('hidden');
    }

    function isGoodFit(job) {
        const rec = (job.recommendation || '').toLowerCase();
        const score = Number(job.fit_score) || 0;
        if (rec.includes('do not apply')) {
            return false;
        }
        if (score < 45) {
            return false;
        }
        return true;
    }

    function displayBulkResults(data) {
        document.getElementById('results-section').classList.add('hidden');
        document.getElementById('bulk-results-section').classList.remove('hidden');
        const meta = document.getElementById('bulk-meta');
        const n = data.listing_count ?? (data.results || []).length;
        meta.textContent = `Compared ${n} posting${n === 1 ? '' : 's'} to your CV (best matches first).`;
        renderBulkResults(data);
        document.getElementById('bulk-results-section').scrollIntoView({ behavior: 'smooth' });
    }

    function renderBulkResults(data) {
        const container = document.getElementById('bulk-job-list');
        container.innerHTML = '';
        const items = data.results || [];
        const filterOn = onlyGoodFits.checked;
        const visible = filterOn ? items.filter(isGoodFit) : items;

        if (visible.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'bulk-empty';
            empty.textContent = filterOn
                ? 'No postings passed the “worth applying” filter. Turn off the filter to see every score, or paste different roles.'
                : 'No results returned.';
            container.appendChild(empty);
            return;
        }

        visible.forEach((job) => {
            const card = document.createElement('article');
            card.className = 'bulk-job-card';
            if (!isGoodFit(job)) {
                card.classList.add('bulk-job-card--weak');
            }

            const score = Number(job.fit_score) || 0;
            const rec = job.recommendation || '—';
            let scoreClass = 'score-pill--warn';
            if (score >= 70) {
                scoreClass = 'score-pill--good';
            } else if (score < 45) {
                scoreClass = 'score-pill--bad';
            }

            card.innerHTML = `
                <div class="bulk-job-card__top">
                    <h3 class="bulk-job-title">${escapeHtml(job.inferred_title || 'Role')}</h3>
                    <span class="score-pill ${scoreClass}">${score}</span>
                </div>
                <p class="bulk-job-rec">${escapeHtml(rec)}</p>
                <p class="bulk-job-verdict">${escapeHtml(job.quick_verdict || '')}</p>
                ${renderFlags(job.red_flags)}
            `;
            container.appendChild(card);
        });
    }

    function renderFlags(flags) {
        if (!flags || !flags.length) {
            return '';
        }
        const lis = flags.map((f) => `<li>${escapeHtml(f)}</li>`).join('');
        return `<div class="bulk-flags"><strong>Flags</strong><ul>${lis}</ul></div>`;
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function displayResults(data) {
        document.getElementById('bulk-results-section').classList.add('hidden');
        document.getElementById('results-section').classList.remove('hidden');

        document.getElementById('category-text').textContent = data.category;
        document.getElementById('seniority-text').textContent = data.seniority || 'Not specified';

        const scoreCircle = document.getElementById('score-circle');
        const scoreText = document.getElementById('score-text');

        setTimeout(() => {
            scoreCircle.setAttribute('stroke-dasharray', `${data.fit_score}, 100`);
            scoreText.textContent = data.fit_score;

            if (data.fit_score >= 70) {
                scoreCircle.style.stroke = 'var(--success)';
            } else if (data.fit_score >= 40) {
                scoreCircle.style.stroke = 'var(--warning)';
            } else {
                scoreCircle.style.stroke = 'var(--danger)';
            }
        }, 100);

        const recText = document.getElementById('rec-text');
        recText.textContent = data.recommendation;

        if (
            data.recommendation.toLowerCase().includes('do not apply') ||
            data.recommendation.toLowerCase().includes('low chance')
        ) {
            recText.style.color = 'var(--danger)';
            recText.style.background = 'rgba(239, 68, 68, 0.1)';
        } else {
            recText.style.color = 'var(--success)';
            recText.style.background = 'rgba(16, 185, 129, 0.1)';
        }

        populateList('missing-list', data.missing_keywords);
        populateList('flags-list', data.red_flags);

        document.getElementById('cv-summary').textContent = data.tailored_summary;
        document.getElementById('cover-letter').textContent = data.cover_letter;
        document.getElementById('recruiter-message').textContent = data.recruiter_message;

        document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });
    }

    function populateList(elementId, items) {
        const ul = document.getElementById(elementId);
        ul.innerHTML = '';
        if (!items || items.length === 0) {
            ul.innerHTML = '<li>None detected</li>';
            return;
        }
        items.forEach((item) => {
            const li = document.createElement('li');
            li.textContent = item;
            ul.appendChild(li);
        });
    }
});

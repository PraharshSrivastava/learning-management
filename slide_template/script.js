document.addEventListener('DOMContentLoaded', () => {
  // --- DOM Elements ---
  const templateItems = document.querySelectorAll('.template-item');
  const slideCanvas = document.getElementById('slide-canvas');
  
  // Editor Inputs
  const inputTitle = document.getElementById('input-title');
  const inputSubtitle = document.getElementById('input-subtitle');
  const inputBullets = document.getElementById('input-bullets');
  const inputDefinition = document.getElementById('input-definition');
  const inputCompHeaderLeft = document.getElementById('input-comp-header-left');
  const inputCompHeaderRight = document.getElementById('input-comp-header-right');
  const inputCompBulletsLeft = document.getElementById('input-comp-bullets-left');
  const inputCompBulletsRight = document.getElementById('input-comp-bullets-right');
  const inputSteps = document.getElementById('input-steps');
  const inputStatValue = document.getElementById('input-stat-value');
  const inputStatLabel = document.getElementById('input-stat-label');
  const inputImageUrl = document.getElementById('input-image-url');

  // Input Groups for Show/Hide
  const groups = {
    title: document.getElementById('group-title'),
    subtitle: document.getElementById('group-subtitle'),
    bullets: document.getElementById('group-bullets'),
    definition: document.getElementById('group-definition'),
    compHeaders: document.getElementById('group-comparison-headers'),
    compContent: document.getElementById('group-comparison-content'),
    steps: document.getElementById('group-steps'),
    stat: document.getElementById('group-stat'),
    image: document.getElementById('group-image'),
  };

  // State
  let currentLayout = 'title';

  // --- Inline Vector Graphics (No broken images, pure design compliance) ---
  const svgAssets = {
    'assets/images/neural_network.png': `
      <svg viewBox="0 0 400 300" width="100%" height="100%" style="background:#0F172A; border-radius:inherit;">
        <!-- Neural Network Lines -->
        <g stroke="rgba(23, 188, 226, 0.2)" stroke-width="2">
          <!-- Input to Hidden -->
          <line x1="80" y1="75" x2="200" y2="60" />
          <line x1="80" y1="75" x2="200" y2="150" />
          <line x1="80" y1="75" x2="200" y2="240" />
          
          <line x1="80" y1="150" x2="200" y2="60" />
          <line x1="80" y1="150" x2="200" y2="150" />
          <line x1="80" y1="150" x2="200" y2="240" />
          
          <line x1="80" y1="225" x2="200" y2="60" />
          <line x1="80" y1="225" x2="200" y2="150" />
          <line x1="80" y1="225" x2="200" y2="240" />

          <!-- Hidden to Output -->
          <line x1="200" y1="60" x2="320" y2="105" />
          <line x1="200" y1="60" x2="320" y2="195" />
          
          <line x1="200" y1="150" x2="320" y2="105" />
          <line x1="200" y1="150" x2="320" y2="195" />
          
          <line x1="200" y1="240" x2="320" y2="105" />
          <line x1="200" y1="240" x2="320" y2="195" />
        </g>
        
        <!-- Nodes Layer -->
        <!-- Input Layer (Navy) -->
        <circle cx="80" cy="75" r="14" fill="#00317A" stroke="#17BCE2" stroke-width="2"/>
        <circle cx="80" cy="150" r="14" fill="#00317A" stroke="#17BCE2" stroke-width="2"/>
        <circle cx="80" cy="225" r="14" fill="#00317A" stroke="#17BCE2" stroke-width="2"/>
        
        <!-- Hidden Layer (Cyan/Orange) -->
        <circle cx="200" cy="60" r="14" fill="#17BCE2" stroke="#FFFFFF" stroke-width="1.5"/>
        <circle cx="200" cy="150" r="14" fill="#F78F20" stroke="#FFFFFF" stroke-width="1.5"/>
        <circle cx="200" cy="240" r="14" fill="#17BCE2" stroke="#FFFFFF" stroke-width="1.5"/>
        
        <!-- Output Layer (Green) -->
        <circle cx="320" cy="105" r="14" fill="#14C496" stroke="#FFFFFF" stroke-width="2"/>
        <circle cx="320" cy="195" r="14" fill="#14C496" stroke="#FFFFFF" stroke-width="2"/>

        <!-- Typography Labels -->
        <text x="80" y="270" font-family="Inter" font-size="10" fill="#AAAAAA" text-anchor="middle" font-weight="bold">INPUTS</text>
        <text x="200" y="270" font-family="Inter" font-size="10" fill="#AAAAAA" text-anchor="middle" font-weight="bold">HIDDEN</text>
        <text x="320" y="270" font-family="Inter" font-size="10" fill="#AAAAAA" text-anchor="middle" font-weight="bold">OUTPUTS</text>
      </svg>
    `,
    'assets/images/ai_workflow.png': `
      <svg viewBox="0 0 400 300" width="100%" height="100%" style="background:#0F172A; border-radius:inherit;">
        <!-- Connecting Arrows -->
        <g stroke="#AAAAAA" stroke-width="3" fill="none">
          <path d="M 85 150 L 125 150" marker-end="url(#arrow)" />
          <path d="M 175 150 L 215 150" />
          <path d="M 265 150 L 305 150" />
        </g>
        
        <!-- Markers -->
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#AAAAAA" />
          </marker>
        </defs>

        <!-- Process blocks -->
        <!-- Sensing -->
        <rect x="25" y="115" width="60" height="70" rx="8" fill="#00317A" stroke="#17BCE2" stroke-width="1.5" />
        <text x="55" y="145" font-family="Inter" font-size="9" fill="#FFFFFF" text-anchor="middle" font-weight="bold">SENSE</text>
        <text x="55" y="165" font-family="Barlow" font-size="7" fill="#EEEEEE" text-anchor="middle">Data Feed</text>
        
        <!-- Assessing -->
        <rect x="115" y="115" width="60" height="70" rx="8" fill="#00317A" stroke="#17BCE2" stroke-width="1.5" />
        <text x="145" y="145" font-family="Inter" font-size="9" fill="#FFFFFF" text-anchor="middle" font-weight="bold">ASSESS</text>
        <text x="145" y="165" font-family="Barlow" font-size="7" fill="#EEEEEE" text-anchor="middle">Vector Match</text>
        
        <!-- Predicting -->
        <rect x="205" y="115" width="60" height="70" rx="8" fill="#00317A" stroke="#F78F20" stroke-width="1.5" />
        <text x="235" y="145" font-family="Inter" font-size="9" fill="#FFFFFF" text-anchor="middle" font-weight="bold">PREDICT</text>
        <text x="235" y="165" font-family="Barlow" font-size="7" fill="#EEEEEE" text-anchor="middle">Weight Neural</text>
        
        <!-- Acting -->
        <rect x="295" y="115" width="60" height="70" rx="8" fill="#00317A" stroke="#14C496" stroke-width="1.5" />
        <text x="325" y="145" font-family="Inter" font-size="9" fill="#FFFFFF" text-anchor="middle" font-weight="bold">ACT</text>
        <text x="325" y="165" font-family="Barlow" font-size="7" fill="#EEEEEE" text-anchor="middle">Output Result</text>

        <text x="200" y="50" font-family="Inter" font-size="14" fill="#FFFFFF" text-anchor="middle" font-weight="bold">COGNITIVE ENGINE WORKFLOW</text>
        <text x="200" y="70" font-family="Barlow" font-size="10" fill="#AAAAAA" text-anchor="middle">4-Stage Pipeline Architecture</text>
      </svg>
    `,
    'assets/images/vector_similarity.png': `
      <svg viewBox="0 0 400 300" width="100%" height="100%" style="background:#0F172A; border-radius:inherit;">
        <!-- Coordinate Grid -->
        <line x1="50" y1="250" x2="350" y2="250" stroke="#475569" stroke-width="2" />
        <line x1="50" y1="50" x2="50" y2="250" stroke="#475569" stroke-width="2" />
        
        <!-- Axis labels -->
        <text x="350" y="270" font-family="Barlow" font-size="10" fill="#94A3B8" text-anchor="end">Dimension X</text>
        <text x="30" y="55" font-family="Barlow" font-size="10" fill="#94A3B8" transform="rotate(-90 30 55)">Dimension Y</text>
        
        <!-- Vectors (Cyan & Orange) -->
        <!-- Vector A (Dog) -->
        <line x1="50" y1="250" x2="250" y2="90" stroke="#17BCE2" stroke-width="4" stroke-linecap="round" />
        <!-- Vector B (Puppy) -->
        <line x1="50" y1="250" x2="290" y2="130" stroke="#F78F20" stroke-width="4" stroke-linecap="round" />
        
        <!-- Vector Labels -->
        <text x="255" y="80" font-family="Inter" font-size="11" fill="#17BCE2" font-weight="bold">Vector A ("Dog")</text>
        <text x="300" y="125" font-family="Inter" font-size="11" fill="#F78F20" font-weight="bold">Vector B ("Puppy")</text>
        
        <!-- Cosine similarity arc -->
        <path d="M 150 250 A 100 100 0 0 0 135 182" fill="none" stroke="#14C496" stroke-width="2" stroke-dasharray="4" />
        <text x="160" y="200" font-family="Barlow" font-size="10" fill="#14C496" font-weight="bold">θ = 12.5°</text>
        <text x="160" y="215" font-family="Inter" font-size="11" fill="#14C496" font-weight="bold">Cosine Similarity = 0.97</text>

        <text x="200" y="30" font-family="Inter" font-size="14" fill="#FFFFFF" text-anchor="middle" font-weight="bold">SEMANTIC VECTOR SPACE</text>
      </svg>
    `
  };

  // --- Toggle Editor Inputs Visibility ---
  function toggleFormGroups() {
    // Hide all first
    Object.values(groups).forEach(g => {
      if (g) g.style.display = 'none';
    });

    // Show based on layout
    switch (currentLayout) {
      case 'title':
        groups.title.style.display = 'flex';
        groups.subtitle.style.display = 'flex';
        break;
      case 'definition':
        groups.definition.style.display = 'flex';
        groups.subtitle.style.display = 'flex'; // Use subtitle as category badge
        break;
      case 'bullets':
        groups.title.style.display = 'flex';
        groups.bullets.style.display = 'flex';
        break;
      case 'bullets_image':
        groups.title.style.display = 'flex';
        groups.bullets.style.display = 'flex';
        groups.image.style.display = 'flex';
        break;
      case 'comparison':
        groups.title.style.display = 'flex';
        groups.compHeaders.style.display = 'flex';
        groups.compContent.style.display = 'flex';
        break;
      case 'image_only':
        groups.title.style.display = 'flex';
        groups.image.style.display = 'flex';
        break;
      case 'process':
        groups.title.style.display = 'flex';
        groups.steps.style.display = 'flex';
        break;
      case 'stat_quote':
        groups.title.style.display = 'flex';
        groups.stat.style.display = 'flex';
        break;
    }
  }

  // --- HTML Slide Creators ---
  
  function getBulletItemsHtml(rawText) {
    if (!rawText.trim()) return '';
    return rawText.split('\n')
      .filter(line => line.trim())
      .map(line => `
        <li class="bullet-item">
          <div class="bullet-dot"></div>
          <span class="bullet-text">${escapeHtml(line)}</span>
        </li>
      `).join('');
  }

  function renderSlide() {
    const titleVal = inputTitle.value;
    const subtitleVal = inputSubtitle.value;
    const bulletsVal = inputBullets.value;
    const definitionVal = inputDefinition.value;
    const compLeftHeader = inputCompHeaderLeft.value;
    const compRightHeader = inputCompHeaderRight.value;
    const compLeftBullets = inputCompBulletsLeft.value;
    const compRightBullets = inputCompBulletsRight.value;
    const stepsVal = inputSteps.value;
    const statValue = inputStatValue.value;
    const statLabel = inputStatLabel.value;
    const imagePreset = inputImageUrl.value;
    
    const vectorSvg = svgAssets[imagePreset] || '';

    let slideHtml = '';

    if (currentLayout === 'title') {
      // 1. Title Slide Layout
      slideHtml = `
        <div class="slide-title-layout">
          <div class="title-top">
            <span class="brand-logo">PHILLIPCAPITAL</span>
            <span class="title-badge">MODULE PRESENTATION</span>
          </div>
          <div class="title-center">
            <span class="title-course-tag">${escapeHtml(subtitleVal)}</span>
            <h1 class="title-hero-text">${escapeHtml(titleVal)}</h1>
          </div>
          <div class="title-bottom">
            <div class="title-bottom-bar"></div>
            <span class="brand-logo" style="opacity: 0.5; font-size:10px;">ESTABLISHED 1975</span>
          </div>
        </div>
      `;
    } 
    else if (currentLayout === 'definition') {
      // 2. Definition Slide
      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-body" style="background-color: #FFFFFF;">
          <div class="slide-definition-layout">
            <div class="definition-quote-box">
              <p class="definition-text">${escapeHtml(definitionVal)}</p>
              <span class="definition-label">${escapeHtml(subtitleVal)}</span>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">Concept Focus</span>
        </div>
      `;
    } 
    else if (currentLayout === 'bullets') {
      // 3. Standard Bullets Layout
      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-header">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body">
          <ul class="bullets-list">
            ${getBulletItemsHtml(bulletsVal)}
          </ul>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">1 / 5</span>
        </div>
      `;
    }
    else if (currentLayout === 'bullets_image') {
      // 4. Bullets + Image Layout
      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-header">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body">
          <div class="bullets-image-split">
            <div class="split-left">
              <ul class="bullets-list">
                ${getBulletItemsHtml(bulletsVal)}
              </ul>
            </div>
            <div class="split-right">
              <div class="slide-image-frame">
                ${vectorSvg}
                <div class="slide-image-caption">
                  Fig: Dynamic graphic representation of slide concept.
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">2 / 5</span>
        </div>
      `;
    }
    else if (currentLayout === 'comparison') {
      // 5. Side-by-Side Comparison Layout
      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-header">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body">
          <div class="comparison-grid">
            <div class="comparison-col">
              <div class="comparison-card-header">${escapeHtml(compLeftHeader)}</div>
              <div class="comparison-card-body">
                <ul class="bullets-list">
                  ${getBulletItemsHtml(compLeftBullets)}
                </ul>
              </div>
            </div>
            <div class="comparison-col right">
              <div class="comparison-card-header">${escapeHtml(compRightHeader)}</div>
              <div class="comparison-card-body">
                <ul class="bullets-list">
                  ${getBulletItemsHtml(compRightBullets)}
                </ul>
              </div>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">3 / 5</span>
        </div>
      `;
    }
    else if (currentLayout === 'image_only') {
      // 6. Image Highlight Layout
      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-header">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body" style="padding-top: 12px; padding-bottom: 12px;">
          <div class="image-highlight-layout">
            <div class="slide-image-frame" style="width: 75%; height: 95%;">
              ${vectorSvg}
              <div class="slide-image-caption">
                Course Visual Highlight: Diagram analysis framework.
              </div>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">4 / 5</span>
        </div>
      `;
    }
    else if (currentLayout === 'process') {
      // 7. Step-by-Step Process Layout
      const parsedSteps = stepsVal.split('\n')
        .filter(line => line.includes('|'))
        .map(line => {
          const parts = line.split('|');
          return { title: parts[0].trim(), text: parts[1].trim() };
        });

      let stepsHtml = '';
      parsedSteps.forEach((step, idx) => {
        stepsHtml += `
          <div class="process-step">
            <span class="step-badge">STEP 0${idx + 1}</span>
            <div class="step-content">
              <h3 class="step-title">${escapeHtml(step.title)}</h3>
              <p class="step-desc">${escapeHtml(step.text)}</p>
            </div>
          </div>
        `;
        if (idx < parsedSteps.length - 1) {
          stepsHtml += `
            <div class="step-arrow">
              <span class="material-symbols-rounded">arrow_right_alt</span>
            </div>
          `;
        }
      });

      slideHtml = `
        <div class="slide-accent-cyan"></div>
        <div class="slide-header">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body">
          <div class="process-timeline">
            ${stepsHtml || '<p style="color:var(--gray);">Add processes in "Title | Desc" format to preview...</p>'}
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">5 / 5</span>
        </div>
      `;
    }
    else if (currentLayout === 'stat_quote') {
      // 8. Big Stat / Quote Layout
      slideHtml = `
        <div class="slide-accent-orange"></div>
        <div class="slide-header" style="background-color: var(--primary-blue)">
          <h1>${escapeHtml(titleVal)}</h1>
          <span class="slide-logo-wordmark">PHILLIPCAPITAL</span>
        </div>
        <div class="slide-body">
          <div class="stat-quote-container">
            <div class="stat-value-box">
              ${escapeHtml(statValue)}
            </div>
            <div class="stat-label-box">
              <p>${escapeHtml(statLabel)}</p>
            </div>
          </div>
        </div>
        <div class="slide-footer">
          <span class="footer-text">PhillipCapital LMS Learning System</span>
          <span class="slide-counter">Metric Focus</span>
        </div>
      `;
    }

    slideCanvas.innerHTML = slideHtml;
  }

  // --- Helper to escape HTML tags ---
  function escapeHtml(text) {
    const map = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
  }

  // --- Event Listeners ---
  
  // Tab Switching
  templateItems.forEach(item => {
    item.addEventListener('click', () => {
      // Remove active from others
      templateItems.forEach(i => i.classList.remove('active'));
      
      // Set active
      item.classList.add('active');
      currentLayout = item.dataset.layout;
      
      toggleFormGroups();
      renderSlide();
    });
  });

  // Editor Inputs Changes
  const allInputs = [
    inputTitle, inputSubtitle, inputBullets, inputDefinition,
    inputCompHeaderLeft, inputCompHeaderRight, inputCompBulletsLeft,
    inputCompBulletsRight, inputSteps, inputStatValue, inputStatLabel,
    inputImageUrl
  ];

  allInputs.forEach(input => {
    if (input) {
      input.addEventListener('input', renderSlide);
      input.addEventListener('change', renderSlide);
    }
  });

  // --- Initial Render ---
  toggleFormGroups();
  renderSlide();
});

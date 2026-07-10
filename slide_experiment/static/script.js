document.addEventListener('DOMContentLoaded', async () => {
    const select = document.getElementById('mock-course-select');
    const startBtn = document.getElementById('start-btn');

    try {
        const res = await fetch('/api/mock-courses');
        const courses = await res.json();
        
        select.innerHTML = '<option value="">-- Select a Course --</option>';
        courses.forEach(course => {
            const opt = document.createElement('option');
            opt.value = course.id;
            opt.textContent = course.name || course.id;
            select.appendChild(opt);
        });
        
        select.addEventListener('change', () => {
            startBtn.disabled = !select.value;
        });
    } catch (err) {
        select.innerHTML = '<option value="">Error loading courses</option>';
        console.error(err);
    }
});

document.getElementById('start-btn').addEventListener('click', async () => {
    const select = document.getElementById('mock-course-select');
    const output = document.getElementById('json-output');
    const courseId = select.value;

    if (!courseId) {
        alert("Please select a course first.");
        return;
    }

    const updateStatus = (id, state) => {
        const el = document.getElementById(id);
        if (el) el.className = state;
    };
    output.textContent = "Starting pipeline at Step 2 (Slide Planner)...";

    // Mark steps 1 as skipped (since mock_data already has it)
    updateStatus('status-upload', 'done');
    updateStatus('status-blueprint', 'done');

    try {
        // Step 5: Slide Planner
        updateStatus('status-slides', 'active');
        output.textContent = "Calling LLM to plan slides for this course (This does 3 passes: Planner, Titles, Image Mapper)...";
        const slidesPlanRes = await fetch(`/api/courses/${courseId}/generate-slides`, { method: 'POST' });
        if (!slidesPlanRes.ok) throw new Error("Slide Planner failed");
        const finalData = await slidesPlanRes.json();
        updateStatus('status-slides', 'done');

        // Step 6: Art Director
        updateStatus('status-art-director', 'active');
        output.textContent = "Calling LLM Art Director to select layouts and generate HTML...";
        const artDirRes = await fetch(`/api/courses/${courseId}/art-director`, { method: 'POST' });
        if (!artDirRes.ok) throw new Error("Art Director failed");
        const artDirData = await artDirRes.json();
        updateStatus('status-art-director', 'done');
        
        const finalCourse = artDirData.course;
        const htmlUrls = artDirData.html_urls;

        // Display Result
        output.textContent = JSON.stringify(finalCourse, null, 2);

        // Update iframe preview if HTML was generated
        const previewContainer = document.getElementById('preview-container');
        const previewPlaceholder = document.getElementById('preview-placeholder');
        const iframe = document.getElementById('slide-preview');
        const moduleSelect = document.getElementById('module-select');
        
        if (htmlUrls && htmlUrls.length > 0) {
            previewPlaceholder.style.display = 'none';
            previewContainer.style.display = 'block';
            
            // Populate module selector
            moduleSelect.innerHTML = '';
            htmlUrls.forEach((url, idx) => {
                const opt = document.createElement('option');
                opt.value = url;
                opt.textContent = `Module ${idx + 1}`;
                moduleSelect.appendChild(opt);
            });
            
            // Handle module switching
            moduleSelect.onchange = (e) => {
                iframe.src = e.target.value;
            };
            
            iframe.src = htmlUrls[0]; // load the first module

            // Setup fullscreen toggle
            const fullscreenBtn = document.getElementById('fullscreen-btn');
            if (fullscreenBtn) {
                fullscreenBtn.onclick = () => {
                    if (iframe.requestFullscreen) {
                        iframe.requestFullscreen();
                    } else if (iframe.webkitRequestFullscreen) { // Safari
                        iframe.webkitRequestFullscreen();
                    } else if (iframe.msRequestFullscreen) { // IE11
                        iframe.msRequestFullscreen();
                    }
                };
            }
        }

        // Display Markdown/Output
        const mdOutput = document.getElementById('markdown-output');
        let combinedOutput = "";
        for (const mod of finalCourse.modules) {
            if (mod.planned_slides && mod.planned_slides.length > 0) {
                for (const slide of mod.planned_slides) {
                    combinedOutput += `## ${slide.title}\n`;
                    combinedOutput += `**Layout:** ${slide.layout_type || 'bullets'}\n\n`;
                    
                    if (slide.content && slide.content.length > 0) {
                        for (const bullet of slide.content) {
                            combinedOutput += `- ${bullet}\n`;
                        }
                    }
                    if (slide.images && slide.images.length > 0) {
                        combinedOutput += `\n**Images on this slide:**\n`;
                        for (const img of slide.images) {
                            combinedOutput += `- [IMAGE: ${img.image_id}]\n`;
                        }
                    }
                    combinedOutput += `\n`;
                }
            }
        }
        mdOutput.textContent = combinedOutput;

    } catch (error) {
        output.textContent = `Error: ${error.message}`;
        console.error(error);
    }
});

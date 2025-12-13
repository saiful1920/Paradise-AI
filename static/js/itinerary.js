let currentItinerary = null;
let budgetChart = null;
let conversationHistory = [];
let pendingChanges = null;

// Load itinerary data on page load
document.addEventListener('DOMContentLoaded', async () => {
    await loadItinerary();
});

async function loadItinerary() {
    const loadingModal = document.getElementById('loadingModal');
    loadingModal.classList.add('show');
    
    try {
        const response = await fetch(`/api/itinerary/${itineraryId}`);
        const data = await response.json();
        
        if (response.ok) {
            currentItinerary = data;
            console.log('📦 Loaded itinerary:', data);
            renderItinerary(data);
        } else {
            alert('Failed to load itinerary');
            window.location.href = '/';
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while loading the itinerary');
    } finally {
        loadingModal.classList.remove('show');
    }
}

function renderItinerary(data) {
    console.log('🎨 Rendering itinerary:', data);
    
    // Update header badge
    const headerBadge = document.getElementById('headerBadge');
    if (headerBadge) {
        headerBadge.textContent = `⭐ ${data.duration} DAY ${data.destination.name.toUpperCase()} ITINERARY`;
    }
    
    // Update trip details
    document.getElementById('detailDestination').textContent = `${data.destination.name}, ${data.destination.country}`;
    document.getElementById('detailBudget').textContent = `$${data.total_budget.toLocaleString()}`;
    document.getElementById('detailDuration').textContent = `${data.duration} Days`;
    document.getElementById('detailTravelers').textContent = data.travelers === 1 ? 'Solo Trip' : `${data.travelers} Adults`;
    
    // Render daily activities with photos
    renderDailyActivities(data.daily_activities);
    
    // Render budget breakdown
    renderBudgetBreakdown(data.budget_breakdown, data.total_budget);
    
    // Render attractions and activities with photos
    renderAttractionsAndActivities(data.attractions_summary);
}

function renderDailyActivities(activities) {
    const activitiesSection = document.getElementById('activitiesSection');
    if (!activitiesSection) {
        console.error('❌ Activities section not found');
        return;
    }
    
    activitiesSection.innerHTML = '';
    console.log(`🎯 Rendering ${activities.length} days of activities`);
    
    let totalPhotos = 0;
    
    activities.forEach(day => {
        const dayCard = document.createElement('div');
        dayCard.className = 'day-card';
        
        let activitiesHTML = '';
        
        if (day.morning) {
            const photoHTML = (day.morning.photo_url && day.morning.photo_url !== 'null' && day.morning.photo_url !== 'undefined') ? 
                `<img src="${day.morning.photo_url}" 
                      alt="${day.morning.name}" 
                      class="activity-photo" 
                      onerror="this.style.display='none'"
                      onload="console.log('✅ Photo loaded: ${day.morning.name}')">` : '';
            
            if (day.morning.photo_url && day.morning.photo_url !== 'null') {
                totalPhotos++;
            }
            
            activitiesHTML += `
                <div class="activity-item">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">☀️ Morning</div>
                            <div class="time-slot">${day.morning.time}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.morning.name}</div>
                        <div class="activity-description">${day.morning.description}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        if (day.afternoon) {
            const photoHTML = (day.afternoon.photo_url && day.afternoon.photo_url !== 'null' && day.afternoon.photo_url !== 'undefined') ? 
                `<img src="${day.afternoon.photo_url}" 
                      alt="${day.afternoon.name}" 
                      class="activity-photo" 
                      onerror="this.style.display='none'"
                      onload="console.log('✅ Photo loaded: ${day.afternoon.name}')">` : '';
            
            if (day.afternoon.photo_url && day.afternoon.photo_url !== 'null') {
                totalPhotos++;
            }
            
            activitiesHTML += `
                <div class="activity-item">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">🌤️ Afternoon</div>
                            <div class="time-slot">${day.afternoon.time}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.afternoon.name}</div>
                        <div class="activity-description">${day.afternoon.description}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        if (day.evening) {
            const photoHTML = (day.evening.photo_url && day.evening.photo_url !== 'null' && day.evening.photo_url !== 'undefined') ? 
                `<img src="${day.evening.photo_url}" 
                      alt="${day.evening.name}" 
                      class="activity-photo" 
                      onerror="this.style.display='none'"
                      onload="console.log('✅ Photo loaded: ${day.evening.name}')">` : '';
            
            if (day.evening.photo_url && day.evening.photo_url !== 'null') {
                totalPhotos++;
            }
            
            activitiesHTML += `
                <div class="activity-item">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">🌙 Evening</div>
                            <div class="time-slot">${day.evening.time}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.evening.name}</div>
                        <div class="activity-description">${day.evening.description}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        dayCard.innerHTML = `
            <h2 class="day-title">${day.title}</h2>
            ${activitiesHTML}
        `;
        
        activitiesSection.appendChild(dayCard);
    });
    
    console.log(`✅ Daily activities rendered with ${totalPhotos} photos`);
}

function renderBudgetBreakdown(budgetBreakdown, totalBudget) {
    const categories = budgetBreakdown.categories;
    
    console.log('💰 Rendering budget breakdown:', categories);
    
    // Update budget amounts
    document.getElementById('budgetFlights').textContent = `$ ${Math.round(categories.flights.amount).toLocaleString()}`;
    document.getElementById('budgetFood').textContent = `$ ${Math.round(categories.food.amount).toLocaleString()}`;
    document.getElementById('budgetHotels').textContent = `$ ${Math.round(categories.hotels.amount).toLocaleString()}`;
    document.getElementById('budgetTravel').textContent = `$ ${Math.round(categories.travel.amount).toLocaleString()}`;
    document.getElementById('budgetActivities').textContent = `$ ${Math.round(categories.activities.amount).toLocaleString()}`;
    
    document.getElementById('totalEstimation').textContent = `$ ${Math.round(budgetBreakdown.total_allocated).toLocaleString()}`;
    document.getElementById('remainingBudget').textContent = `$ ${Math.round(budgetBreakdown.remaining_budget).toLocaleString()}`;
    
    // Create or update chart
    const ctx = document.getElementById('budgetChart');
    if (!ctx) {
        console.error('❌ Budget chart canvas not found');
        return;
    }
    
    const chartContext = ctx.getContext('2d');
    
    if (budgetChart) {
        budgetChart.destroy();
    }
    
    budgetChart = new Chart(chartContext, {
        type: 'doughnut',
        data: {
            labels: ['Flights', 'Hotels', 'Activities', 'Food', 'Travel'],
            datasets: [{
                data: [
                    categories.flights.percentage,
                    categories.hotels.percentage,
                    categories.activities.percentage,
                    categories.food.percentage,
                    categories.travel.percentage
                ],
                backgroundColor: [
                    '#3b82f6',
                    '#8b5cf6',
                    '#ec4899',
                    '#10b981',
                    '#f59e0b'
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            }
        }
    });
    
    console.log('✅ Budget breakdown rendered');
}

function renderAttractionsAndActivities(summary) {
    console.log('🎭 Rendering attractions and activities:', summary);
    
    // Render attractions
    const attractionsDescription = document.getElementById('attractionsDescription');
    const attractionsList = document.getElementById('attractionsList');
    
    if (attractionsDescription && attractionsList) {
        attractionsDescription.textContent = summary.attractions.description;
        attractionsList.innerHTML = summary.attractions.items.map(item => `<li>${item}</li>`).join('');
        
        const attractionCard = document.querySelector('.attraction-card:first-child .attraction-image');
        if (attractionCard) {
            const hasPhotos = summary.attractions.photos && 
                             summary.attractions.photos.length > 0 && 
                             summary.attractions.photos[0] &&
                             summary.attractions.photos[0] !== 'null';
            
            if (hasPhotos) {
                attractionCard.src = summary.attractions.photos[0];
                attractionCard.alt = 'Attractions in ' + currentItinerary.destination.name;
                attractionCard.onerror = function() {
                    this.src = 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=300&fit=crop';
                };
            } else {
                attractionCard.src = 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=300&fit=crop';
            }
        }
    }
    
    // Render activities
    const activitiesDescription = document.getElementById('activitiesDescription');
    const activitiesList = document.getElementById('activitiesList');
    
    if (activitiesDescription && activitiesList) {
        activitiesDescription.textContent = summary.activities.description;
        activitiesList.innerHTML = summary.activities.items.map(item => `<li>${item}</li>`).join('');
        
        const activityCard = document.querySelector('.attraction-card:last-child .attraction-image');
        if (activityCard) {
            const hasPhotos = summary.activities.photos && 
                             summary.activities.photos.length > 0 && 
                             summary.activities.photos[0] &&
                             summary.activities.photos[0] !== 'null';
            
            if (hasPhotos) {
                activityCard.src = summary.activities.photos[0];
                activityCard.alt = 'Activities in ' + currentItinerary.destination.name;
                activityCard.onerror = function() {
                    this.src = 'https://images.unsplash.com/photo-1527631746610-bca00a040d60?w=400&h=300&fit=crop';
                };
            } else {
                activityCard.src = 'https://images.unsplash.com/photo-1527631746610-bca00a040d60?w=400&h=300&fit=crop';
            }
        }
    }
}

// Photo upload handler
async function handlePhotoUpload(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    console.log('📤 Uploading photo:', file.name);
    
    const formData = new FormData();
    formData.append('file', file);
    
    const uploadStatus = document.getElementById('uploadStatus');
    uploadStatus.textContent = 'Uploading...';
    
    try {
        const response = await fetch('/api/upload-photo', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            uploadedPhotoFilename = data.filename;
            
            // Show preview
            const preview = document.getElementById('uploadPreview');
            preview.src = data.url;
            preview.style.display = 'block';
            
            // Enable generate button
            document.getElementById('generateVideoBtn').disabled = false;
            document.getElementById('generateVideoBtn').textContent = '🎬 Generate Video';
            
            uploadStatus.textContent = '✅ Photo uploaded successfully!';
            uploadStatus.style.color = '#10b981';
            
            console.log('✅ Photo uploaded:', data.filename);
        } else {
            throw new Error('Upload failed');
        }
    } catch (error) {
        console.error('❌ Upload error:', error);
        uploadStatus.textContent = '❌ Upload failed. Please try again.';
        uploadStatus.style.color = '#ef4444';
    }
}

// Video generation
async function generateVideo() {
    if (!uploadedPhotoFilename) {
        alert('Please upload your photo first!');
        return;
    }
    
    console.log('🎥 Starting video generation...');
    
    const loadingModal = document.getElementById('loadingModal');
    loadingModal.classList.add('show');
    loadingModal.querySelector('p').textContent = 'Generating your travel video...';
    
    try {
        const response = await fetch('/api/generate-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                user_photo_filename: uploadedPhotoFilename
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Video generation started:', data.video_id);
            
            // Redirect to video status page
            window.location.href = `/video/${data.video_id}`;
        } else {
            throw new Error('Failed to start video generation');
        }
    } catch (error) {
        console.error('❌ Error:', error);
        alert('Failed to generate video. Please try again.');
    } finally {
        loadingModal.classList.remove('show');
    }
}

// Budget reallocation
async function reallocateBudget() {
    const checkboxes = document.querySelectorAll('.reallocation-checkbox input[type="checkbox"]:checked');
    const selectedCategories = Array.from(checkboxes).map(cb => cb.value);
    
    if (selectedCategories.length === 0) {
        alert('Please select at least one category to reallocate budget to');
        return;
    }
    
    const loadingModal = document.getElementById('loadingModal');
    loadingModal.classList.add('show');
    
    try {
        const response = await fetch('/api/reallocate-budget', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                selected_categories: selectedCategories
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentItinerary.budget_breakdown = data.budget_breakdown;
            renderBudgetBreakdown(data.budget_breakdown, currentItinerary.total_budget);
            
            checkboxes.forEach(cb => cb.checked = false);
            
            alert('Budget reallocated successfully!');
        } else {
            throw new Error('Failed to reallocate budget');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred while reallocating budget');
    } finally {
        loadingModal.classList.remove('show');
    }
}

// Chat functionality
function toggleChat() {
    const chatWindow = document.getElementById('chatWindow');
    chatWindow.classList.toggle('show');
}

function minimizeChat() {
    const chatWindow = document.getElementById('chatWindow');
    chatWindow.classList.remove('show');
}

function handleChatKeyPress(event) {
    if (event.key === 'Enter') {
        sendMessage();
    }
}

async function sendMessage() {
    const chatInput = document.getElementById('chatInput');
    const message = chatInput.value.trim();
    
    if (!message) return;
    
    addMessageToChat('user', message);
    chatInput.value = '';
    
    conversationHistory.push({
        role: 'user',
        content: message
    });
    
    const loadingId = addLoadingMessage();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                message: message,
                conversation_history: conversationHistory
            })
        });
        
        const data = await response.json();
        
        removeLoadingMessage(loadingId);
        
        if (response.ok) {
            addMessageToChat('bot', data.response);
            
            conversationHistory.push({
                role: 'assistant',
                content: data.response
            });
            
            // Handle budget warnings
            if (data.budget_warning) {
                addMessageToChat('bot', `⚠️ Budget Alert: Your proposed changes require a minimum budget of $${data.minimum_budget.toLocaleString()}. Would you like to increase your budget to proceed?`);
                return;
            }
            
            if (data.requires_confirmation && data.proposed_changes) {
                pendingChanges = data.proposed_changes;
                showConfirmationButtons();
            }
            
            if (data.modifications_made && data.updated_itinerary) {
                console.log('🔄 Updating itinerary with new data');
                currentItinerary = data.updated_itinerary;
                renderItinerary(currentItinerary);
                
                setTimeout(() => {
                    addMessageToChat('bot', '✅ Your itinerary has been updated! Scroll up to see the changes.');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }, 500);
            }
        } else {
            throw new Error('Failed to send message');
        }
    } catch (error) {
        console.error('Error:', error);
        removeLoadingMessage(loadingId);
        addMessageToChat('bot', 'Sorry, I encountered an error. Please try again.');
    }
}

function showConfirmationButtons() {
    const chatMessages = document.getElementById('chatMessages');
    const buttonsDiv = document.createElement('div');
    buttonsDiv.className = 'confirmation-buttons';
    buttonsDiv.innerHTML = `
        <div class="confirmation-text">Would you like to apply these changes?</div>
        <div class="button-group">
            <button class="btn-confirm" onclick="confirmChanges()">✅ Yes, Apply Changes</button>
            <button class="btn-cancel" onclick="cancelChanges()">❌ No, Cancel</button>
        </div>
    `;
    chatMessages.appendChild(buttonsDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function confirmChanges() {
    if (!pendingChanges) return;
    
    addMessageToChat('user', 'Yes, please apply the changes');
    conversationHistory.push({
        role: 'user',
        content: 'Yes, please apply the changes'
    });
    
    const buttons = document.querySelector('.confirmation-buttons');
    if (buttons) buttons.remove();
    
    const loadingId = addLoadingMessage();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                message: 'yes, confirm and apply the changes',
                conversation_history: conversationHistory
            })
        });
        
        const data = await response.json();
        
        removeLoadingMessage(loadingId);
        
        if (response.ok) {
            addMessageToChat('bot', data.response);
            conversationHistory.push({
                role: 'assistant',
                content: data.response
            });
            
            // Handle budget warnings
            if (data.budget_warning) {
                addMessageToChat('bot', `⚠️ Budget Alert: Your proposed changes require a minimum budget of $${data.minimum_budget.toLocaleString()}. Would you like to increase your budget to proceed?`);
                pendingChanges = null;
                return;
            }
            
            if (data.modifications_made && data.updated_itinerary) {
                console.log('🔄 Updating itinerary with confirmed changes');
                currentItinerary = data.updated_itinerary;
                renderItinerary(currentItinerary);
                
                setTimeout(() => {
                    addMessageToChat('bot', '✅ Changes applied successfully! Scroll up to see your updated itinerary.');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }, 100);
            }
        } else {
            throw new Error('Failed to apply changes');
        }
    } catch (error) {
        console.error('Error:', error);
        removeLoadingMessage(loadingId);
        addMessageToChat('bot', 'Sorry, there was an error applying your changes.');
    }
    
    pendingChanges = null;
}

function cancelChanges() {
    addMessageToChat('user', 'No, cancel the changes');
    conversationHistory.push({
        role: 'user',
        content: 'No, cancel the changes'
    });
    
    addMessageToChat('bot', 'Okay, I cancelled the changes. What would you like to do instead?');
    conversationHistory.push({
        role: 'assistant',
        content: 'Okay, I cancelled the changes.'
    });
    
    const buttons = document.querySelector('.confirmation-buttons');
    if (buttons) buttons.remove();
    
    pendingChanges = null;
}

function addMessageToChat(sender, content) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${sender}-message`;
    
    const avatar = sender === 'bot' ? '🤖' : '👤';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">${content}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addLoadingMessage() {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = 'chat-message bot-message';
    messageDiv.id = 'loading-message';
    
    messageDiv.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return 'loading-message';
}

function removeLoadingMessage(id) {
    const loadingMessage = document.getElementById(id);
    if (loadingMessage) {
        loadingMessage.remove();
    }
}

// PDF Download Functionality
async function downloadItineraryAsPDF() {
    const button = document.getElementById('downloadPdfBtn');
    const originalText = button.innerHTML;
    
    // Disable button and show loading
    button.disabled = true;
    button.innerHTML = '<span class="download-icon">⏳</span><span>Generating PDF...</span>';
    
    try {
        console.log('📄 Starting PDF generation...');
        
        // Get the itinerary container
        const element = document.getElementById('itineraryContent');
        
        // Add class to temporarily hide chat and video section
        document.body.classList.add('pdf-generating');
        
        // Get destination name for filename
        const destination = currentItinerary?.destination?.name || 'Itinerary';
        const sanitizedDestination = destination.replace(/[^a-z0-9]/gi, '_');
        const filename = `${sanitizedDestination}_Travel_Itinerary.pdf`;
        
        // PDF options for high quality output
        const opt = {
            margin: [10, 10, 10, 10],
            filename: filename,
            image: { type: 'jpeg', quality: 0.95 },
            html2canvas: { 
                scale: 2,
                useCORS: true,
                logging: false,
                letterRendering: true,
                scrollY: 0,
                scrollX: 0
            },
            jsPDF: { 
                unit: 'mm', 
                format: 'a4', 
                orientation: 'portrait',
                compress: true
            },
            pagebreak: { 
                mode: ['avoid-all', 'css', 'legacy'],
                before: '.day-card',
                avoid: ['.budget-chart-container', '.detail-item']
            }
        };
        
        console.log('📄 Generating PDF with options:', opt);
        
        // Generate PDF
        await html2pdf().set(opt).from(element).save();
        
        console.log('✅ PDF generated successfully!');
        
        // Show success message
        button.innerHTML = '<span class="download-icon">✅</span><span>Downloaded!</span>';
        
        // Reset button after 2 seconds
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText;
            document.body.classList.remove('pdf-generating');
        }, 2000);
        
    } catch (error) {
        console.error('❌ Error generating PDF:', error);
        
        // Show error state
        button.innerHTML = '<span class="download-icon">❌</span><span>Error! Try Again</span>';
        
        // Reset button after 2 seconds
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText;
            document.body.classList.remove('pdf-generating');
        }, 2000);
        
        alert('Failed to generate PDF. Please try again.');
    }
}
// Budget slider functionality
const budgetSlider = document.getElementById('budget');
const budgetValue = document.getElementById('budgetValue');
const durationSelect = document.getElementById('duration');
const durationHint = document.getElementById('durationHint');

console.log('🎨 Initializing Travel Itinerary Generator v2.0');

// Update budget display
budgetSlider.addEventListener('input', (e) => {
    const value = e.target.value;
    budgetValue.textContent = `$ ${parseInt(value).toLocaleString()}`;
    
    // Update slider gradient
    const percentage = ((value - budgetSlider.min) / (budgetSlider.max - budgetSlider.min)) * 100;
    budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${percentage}%, #e2e8f0 ${percentage}%, #e2e8f0 100%)`;
    
    // Position the value bubble
    budgetValue.style.left = `${percentage}%`;
});

// Duration change - update hint about cities
durationSelect.addEventListener('change', (e) => {
    const duration = parseInt(e.target.value);
    let hint = '';
    
    if (duration <= 3) {
        hint = `${duration} days = 1 city recommended`;
    } else if (duration <= 5) {
        hint = `${duration} days = 1-2 cities possible`;
    } else if (duration <= 7) {
        hint = `${duration} days = 2-3 cities possible`;
    } else if (duration <= 14) {
        hint = `${duration} days = 3-4 cities possible`;
    } else {
        hint = `${duration} days = 4+ cities possible`;
    }
    
    durationHint.textContent = hint;
    console.log(`📅 Duration changed: ${hint}`);
});

// Activity preference buttons
const activityButtons = document.querySelectorAll('.activity-btn');
let selectedActivity = 'relaxed';

activityButtons.forEach(btn => {
    btn.addEventListener('click', (e) => {
        activityButtons.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        selectedActivity = btn.dataset.value;
        console.log(`🎯 Activity preference set to: ${selectedActivity}`);
    });
});

// Form submission
const form = document.getElementById('itineraryForm');
const loadingModal = document.getElementById('loadingModal');
const loadingMessage = document.getElementById('loadingMessage');
const loadingHint = document.getElementById('loadingHint');
const budgetModal = document.getElementById('budgetModal');
const budgetMessage = document.getElementById('budgetMessage');
const budgetBreakdownPreview = document.getElementById('budgetBreakdownPreview');
const submitBtn = document.getElementById('submitBtn');
let minimumBudgetRequired = 0;
let budgetBreakdownData = null;

// Loading messages rotation
const loadingMessages = [
    { msg: "Analyzing your destination...", hint: "Finding the best cities to visit" },
    { msg: "Searching for experiences...", hint: "Looking for tours, classes, and excursions" },
    { msg: "Finding the best hotels...", hint: "Comparing prices and ratings" },
    { msg: "Discovering local restaurants...", hint: "Finding authentic dining experiences" },
    { msg: "Calculating optimal routes...", hint: "Planning the perfect daily schedule" },
    { msg: "Searching for flights...", hint: "Finding the best deals" },
    { msg: "Creating your personalized itinerary...", hint: "Almost ready!" }
];

let loadingInterval = null;
let loadingIndex = 0;

function startLoadingAnimation() {
    loadingIndex = 0;
    updateLoadingMessage();
    loadingInterval = setInterval(() => {
        loadingIndex = (loadingIndex + 1) % loadingMessages.length;
        updateLoadingMessage();
    }, 3000);
}

function updateLoadingMessage() {
    loadingMessage.textContent = loadingMessages[loadingIndex].msg;
    loadingHint.textContent = loadingMessages[loadingIndex].hint;
}

function stopLoadingAnimation() {
    if (loadingInterval) {
        clearInterval(loadingInterval);
        loadingInterval = null;
    }
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    console.log('=' .repeat(80));
    console.log('📝 Form Submission Started');
    console.log('=' .repeat(80));
    
    // Get form values
    const userLocation = document.getElementById('userLocation').value.trim();
    const destination = document.getElementById('destination').value.trim();
    const budget = parseFloat(budgetSlider.value);
    const includeFlights = document.getElementById('includeFlights').checked;
    const includeHotels = document.getElementById('includeHotels').checked;
    const duration = parseInt(document.getElementById('duration').value);
    const travelers = parseInt(document.getElementById('travelers').value);
    
    // Log form values
    console.log('📋 Form Data:');
    console.log(`   User Location: ${userLocation}`);
    console.log(`   Destination: ${destination}`);
    console.log(`   Budget: $${budget.toLocaleString()}`);
    console.log(`   Duration: ${duration} days`);
    console.log(`   Travelers: ${travelers}`);
    console.log(`   Include Flights: ${includeFlights}`);
    console.log(`   Include Hotels: ${includeHotels}`);
    console.log(`   Activity Level: ${selectedActivity}`);
    
    // Validation
    if (!userLocation) {
        console.error('❌ Validation failed: No origin location entered');
        alert('Please enter where you are traveling from');
        document.getElementById('userLocation').focus();
        return;
    }
    
    if (!destination) {
        console.error('❌ Validation failed: No destination entered');
        alert('Please enter a destination');
        document.getElementById('destination').focus();
        return;
    }
    
    if (!duration) {
        console.error('❌ Validation failed: No duration selected');
        alert('Please select trip duration');
        return;
    }
    
    if (!travelers) {
        console.error('❌ Validation failed: No travelers selected');
        alert('Please select number of travelers');
        return;
    }
    
    console.log('✅ Form validation passed');
    
    // Show loading modal with animation
    loadingModal.classList.add('show');
    startLoadingAnimation();
    submitBtn.disabled = true;
    console.log('⏳ Sending request to backend...');
    
    const requestData = {
        destination,
        budget,
        activity_preference: selectedActivity,
        include_flights: includeFlights,
        include_hotels: includeHotels,
        duration,
        travelers,
        current_location: userLocation
    };
    
    console.log('📤 Request payload:', requestData);
    
    try {
        const startTime = Date.now();
        
        const response = await fetch('/api/create-itinerary', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestData)
        });
        
        const responseTime = Date.now() - startTime;
        console.log(`⏱️  Response received in ${responseTime}ms`);
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Itinerary created successfully!');
            console.log(`🆔 Itinerary ID: ${data.itinerary_id}`);
            
            // Log cities if multi-city
            if (data.itinerary?.destination?.cities) {
                console.log(`🏙️ Cities: ${data.itinerary.destination.cities.join(', ')}`);
            }
            
            // Log photo and experience statistics
            if (data.itinerary?.daily_activities) {
                const photoCount = data.itinerary.daily_activities.reduce((count, day) => {
                    return count + 
                        (day.morning?.photo_url ? 1 : 0) +
                        (day.afternoon?.photo_url ? 1 : 0) +
                        (day.evening?.photo_url ? 1 : 0);
                }, 0);
                console.log(`📸 Photos in itinerary: ${photoCount}`);
            }
            
            if (data.itinerary?.recommended_experiences) {
                const expCount = Object.values(data.itinerary.recommended_experiences)
                    .reduce((sum, cat) => sum + (cat.count || 0), 0);
                console.log(`🎭 Experiences available: ${expCount}`);
            }
            
            console.log('🔄 Redirecting to itinerary page...');
            console.log('=' .repeat(80));
            
            // Success - redirect to itinerary page
            window.location.href = `/itinerary/${data.itinerary_id}`;
        } else if (response.status === 400 && data.error === 'insufficient_budget') {
            console.warn('⚠️  Insufficient budget detected');
            console.log(`   Current: $${data.current_budget}`);
            console.log(`   Minimum Required: $${data.minimum_budget}`);
            
            // Stop loading
            stopLoadingAnimation();
            loadingModal.classList.remove('show');
            
            // Store data for adjustment
            minimumBudgetRequired = data.minimum_budget;
            budgetBreakdownData = data.breakdown;
            
            // Show budget breakdown preview
            if (budgetBreakdownData) {
                budgetBreakdownPreview.innerHTML = `
                    <h4>Estimated Minimum Costs:</h4>
                    <ul class="budget-preview-list">
                        ${budgetBreakdownData.flights ? `<li>✈️ Flights: $${Math.round(budgetBreakdownData.flights).toLocaleString()}</li>` : ''}
                        ${budgetBreakdownData.hotels ? `<li>🏨 Hotels: $${Math.round(budgetBreakdownData.hotels).toLocaleString()}</li>` : ''}
                        <li>🍔 Food: $${Math.round(budgetBreakdownData.food || 0).toLocaleString()}</li>
                        <li>🎭 Activities: $${Math.round(budgetBreakdownData.activities || 0).toLocaleString()}</li>
                        <li>🚗 Transport: $${Math.round(budgetBreakdownData.transport || 0).toLocaleString()}</li>
                    </ul>
                    <p class="budget-preview-total">Total Minimum: <strong>$${Math.round(data.minimum_budget).toLocaleString()}</strong></p>
                `;
            }
            
            budgetMessage.textContent = data.message;
            budgetModal.classList.add('show');
            
            console.log('💡 Showing budget adjustment modal');
        } else {
            throw new Error(data.detail || 'Failed to create itinerary');
        }
    } catch (error) {
        console.error('❌ Error creating itinerary:', error);
        console.error('   Error details:', error.message);
        console.log('=' .repeat(80));
        
        alert('An error occurred while creating your itinerary. Please try again.');
        stopLoadingAnimation();
        loadingModal.classList.remove('show');
    } finally {
        submitBtn.disabled = false;
    }
});

// Close budget modal
function closeBudgetModal() {
    console.log('✕ Closing budget modal');
    budgetModal.classList.remove('show');
}

// Adjust budget
function adjustBudget() {
    console.log('💰 Adjusting budget to minimum required');
    const newBudget = Math.ceil(minimumBudgetRequired / 100) * 100; // Round up to nearest 100
    console.log(`   New budget: $${newBudget}`);
    
    budgetModal.classList.remove('show');
    
    // Ensure budget doesn't exceed slider max
    const maxBudget = parseInt(budgetSlider.max);
    const adjustedBudget = Math.min(newBudget, maxBudget);
    
    if (newBudget > maxBudget) {
        // Need to increase slider max
        budgetSlider.max = Math.ceil(newBudget / 1000) * 1000;
        console.log(`   Increased slider max to: $${budgetSlider.max}`);
    }
    
    // Set budget slider to adjusted value
    budgetSlider.value = adjustedBudget;
    budgetValue.textContent = `$ ${adjustedBudget.toLocaleString()}`;
    
    // Update slider gradient
    const percentage = ((adjustedBudget - budgetSlider.min) / (budgetSlider.max - budgetSlider.min)) * 100;
    budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${percentage}%, #e2e8f0 ${percentage}%, #e2e8f0 100%)`;
    budgetValue.style.left = `${percentage}%`;
    
    // Scroll to budget section
    budgetSlider.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Highlight the budget section briefly
    budgetSlider.parentElement.classList.add('highlight');
    setTimeout(() => {
        budgetSlider.parentElement.classList.remove('highlight');
    }, 2000);
    
    console.log('✅ Budget adjusted successfully');
}

// Initial slider setup
const initialPercentage = ((budgetSlider.value - budgetSlider.min) / (budgetSlider.max - budgetSlider.min)) * 100;
budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${initialPercentage}%, #e2e8f0 ${initialPercentage}%, #e2e8f0 100%)`;

// Set initial duration hint
durationSelect.dispatchEvent(new Event('change'));

console.log('✅ Application initialized successfully');
console.log('💡 Features: Multi-city support, Experiences, Detailed Budget Breakdown');
console.log('=' .repeat(80));
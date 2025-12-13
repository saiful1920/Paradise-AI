// Budget slider functionality
const budgetSlider = document.getElementById('budget');
const budgetValue = document.getElementById('budgetValue');

console.log('🎨 Initializing Travel Itinerary Generator');

budgetSlider.addEventListener('input', (e) => {
    const value = e.target.value;
    budgetValue.textContent = `$ ${parseInt(value).toLocaleString()}`;
    
    // Update slider gradient
    const percentage = (value / budgetSlider.max) * 100;
    budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${percentage}%, #e2e8f0 ${percentage}%, #e2e8f0 100%)`;
    
    // Position the value bubble
    const position = (value / budgetSlider.max) * 100;
    budgetValue.style.left = `${position}%`;
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
const budgetModal = document.getElementById('budgetModal');
const budgetMessage = document.getElementById('budgetMessage');
const submitBtn = document.getElementById('submitBtn');
let minimumBudgetRequired = 0;

form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    console.log('=' .repeat(80));
    console.log('📝 Form Submission Started');
    console.log('=' .repeat(80));
    
    // Get form values
    const destination = document.getElementById('destination').value.trim();
    const budget = parseFloat(budgetSlider.value);
    const includeFlights = document.getElementById('includeFlights').checked;
    const includeHotels = document.getElementById('includeHotels').checked;
    const duration = parseInt(document.getElementById('duration').value);
    const travelers = parseInt(document.getElementById('travelers').value);
    
    // Log form values
    console.log('📋 Form Data:');
    console.log(`   Destination: ${destination}`);
    console.log(`   Budget: $${budget.toLocaleString()}`);
    console.log(`   Duration: ${duration} days`);
    console.log(`   Travelers: ${travelers}`);
    console.log(`   Include Flights: ${includeFlights}`);
    console.log(`   Include Hotels: ${includeHotels}`);
    console.log(`   Activity Level: ${selectedActivity}`);
    
    // Validation
    if (!destination) {
        console.error('❌ Validation failed: No destination entered');
        alert('Please enter a destination');
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
    
    // Show loading modal
    loadingModal.classList.add('show');
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
        user_location: 'New York'
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
            
            // Log photo statistics
            if (data.itinerary && data.itinerary.daily_activities) {
                const photoCount = data.itinerary.daily_activities.reduce((count, day) => {
                    return count + 
                        (day.morning?.photo_url ? 1 : 0) +
                        (day.afternoon?.photo_url ? 1 : 0) +
                        (day.evening?.photo_url ? 1 : 0);
                }, 0);
                console.log(`📸 Photos in itinerary: ${photoCount}`);
            }
            
            console.log('🔄 Redirecting to itinerary page...');
            console.log('=' .repeat(80));
            
            // Success - redirect to itinerary page
            window.location.href = `/itinerary/${data.itinerary_id}`;
        } else if (response.status === 400 && data.error === 'insufficient_budget') {
            console.warn('⚠️  Insufficient budget detected');
            console.log(`   Current: $${data.current_budget}`);
            console.log(`   Minimum Required: $${data.minimum_budget}`);
            
            // Budget insufficient
            loadingModal.classList.remove('show');
            minimumBudgetRequired = data.minimum_budget;
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
    console.log(`   New budget: $${Math.ceil(minimumBudgetRequired)}`);
    
    budgetModal.classList.remove('show');
    
    // Set budget slider to minimum required
    budgetSlider.value = Math.ceil(minimumBudgetRequired);
    budgetValue.textContent = `$ ${Math.ceil(minimumBudgetRequired).toLocaleString()}`;
    
    // Update slider gradient
    const percentage = (budgetSlider.value / budgetSlider.max) * 100;
    budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${percentage}%, #e2e8f0 ${percentage}%, #e2e8f0 100%)`;
    
    const position = (budgetSlider.value / budgetSlider.max) * 100;
    budgetValue.style.left = `${position}%`;
    
    // Scroll to budget section
    budgetSlider.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    console.log('✅ Budget adjusted successfully');
}

// Initial slider setup
const initialPercentage = (budgetSlider.value / budgetSlider.max) * 100;
budgetSlider.style.background = `linear-gradient(to right, #667eea 0%, #667eea ${initialPercentage}%, #e2e8f0 ${initialPercentage}%, #e2e8f0 100%)`;

console.log('✅ Application initialized successfully');
console.log('💡 Open browser console to see detailed logs');
console.log('=' .repeat(80));
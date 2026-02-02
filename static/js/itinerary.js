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
        headerBadge.textContent = data.main_title || `⭐ ${data.duration} DAY ${data.destination.name.toUpperCase()} ITINERARY`;
    }
    
    // Handle multi-city display
    const multiCityBadge = document.getElementById('multiCityBadge');
    const cityList = document.getElementById('cityList');
    
    if (data.destination.is_multi_city && data.destination.cities && data.destination.cities.length > 1) {
        multiCityBadge.style.display = 'flex';
        cityList.innerHTML = data.destination.cities
            .map(city => `<span class="city-tag">${city}</span>`)
            .join(' → ');
        console.log(`🏙️ Multi-city trip: ${data.destination.cities.join(' → ')}`);
    } else {
        multiCityBadge.style.display = 'none';
    }
    
    // Update trip details
    const destinationText = data.destination.cities && data.destination.cities.length > 1
        ? `${data.destination.cities.join(', ')}, ${data.destination.country}`
        : `${data.destination.name}, ${data.destination.country}`;
    
    document.getElementById('detailDestination').textContent = destinationText;
    document.getElementById('detailBudget').textContent = `$${data.total_budget.toLocaleString()}`;
    document.getElementById('detailDuration').textContent = `${data.duration} Days`;
    document.getElementById('detailTravelers').textContent = data.travelers === 1 ? 'Solo Trip' : `${data.travelers} Adults`;
    
    // Render daily activities
    renderDailyActivities(data.daily_activities);
    
    // Render recommended experiences
    if (data.recommended_experiences) {
        renderRecommendedExperiences(data.recommended_experiences);
    }
    
    // Render flight recommendations
    if (data.updated_flights && data.updated_flights.length > 0) {
        renderFlightRecommendations(data.updated_flights);
    }
    
    // Render hotel recommendations
    if (data.hotel_recommendations && data.hotel_recommendations.length > 0) {
        renderHotelRecommendations(data.hotel_recommendations);
    }
    
    // Render restaurant recommendations
    if (data.restaurant_recommendations && data.restaurant_recommendations.length > 0) {
        renderRestaurantRecommendations(data.restaurant_recommendations);
    }
    
    // Render budget breakdown
    renderBudgetBreakdown(data.budget_breakdown, data.total_budget);
    
    // Render attractions and activities summary
    if (data.attractions_summary) {
        renderAttractionsAndActivities(data.attractions_summary);
    }
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
    let currentCity = null;
    
    activities.forEach(day => {
        const dayCard = document.createElement('div');
        dayCard.className = 'day-card';
        dayCard.id = `day-${day.day}`;
        
        // City change indicator
        let cityBadgeHTML = '';
        if (day.city && day.city !== currentCity) {
            currentCity = day.city;
            cityBadgeHTML = `<div class="day-city-badge">📍 ${day.city}</div>`;
        }
        
        let activitiesHTML = '';
        
        // Morning activity
        if (day.morning) {
            const photoHTML = getPhotoHTML(day.morning);
            if (day.morning.photo_url) totalPhotos++;
            
            activitiesHTML += `
                <div class="activity-item" data-day="${day.day}" data-slot="morning">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">☀️ Morning</div>
                            <div class="time-slot">${day.morning.time || '09:00 - 12:00'}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.morning.name}</div>
                        <div class="activity-description">${day.morning.description || ''}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        // Afternoon activity
        if (day.afternoon) {
            const photoHTML = getPhotoHTML(day.afternoon);
            if (day.afternoon.photo_url) totalPhotos++;
            
            activitiesHTML += `
                <div class="activity-item" data-day="${day.day}" data-slot="afternoon">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">🌤️ Afternoon</div>
                            <div class="time-slot">${day.afternoon.time || '14:00 - 17:30'}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.afternoon.name}</div>
                        <div class="activity-description">${day.afternoon.description || ''}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        // Evening activity
        if (day.evening) {
            const photoHTML = getPhotoHTML(day.evening);
            if (day.evening.photo_url) totalPhotos++;
            
            activitiesHTML += `
                <div class="activity-item" data-day="${day.day}" data-slot="evening">
                    <div class="activity-time">
                        <div class="time-dot"></div>
                        <div>
                            <div class="time-label">🌙 Evening</div>
                            <div class="time-slot">${day.evening.time || '19:00 - 22:00'}</div>
                        </div>
                    </div>
                    <div class="activity-details">
                        <div class="activity-name">${day.evening.name}</div>
                        <div class="activity-description">${day.evening.description || ''}</div>
                        ${photoHTML}
                    </div>
                </div>
            `;
        }
        
        dayCard.innerHTML = `
            ${cityBadgeHTML}
            <h2 class="day-title">${day.title}</h2>
            <div class="day-date">${day.date || ''}</div>
            ${activitiesHTML}
        `;
        
        activitiesSection.appendChild(dayCard);
    });
    
    console.log(`✅ Daily activities rendered with ${totalPhotos} photos`);
}

function getPhotoHTML(activity) {
    if (!activity.photo_url || activity.photo_url === 'null' || activity.photo_url === 'undefined') {
        return '';
    }
    return `<img src="${activity.photo_url}" 
                  alt="${activity.name}" 
                  class="activity-photo" 
                  onerror="this.style.display='none'">`;
}

function renderRecommendedExperiences(experiences) {
    const experiencesGrid = document.getElementById('experiencesGrid');
    const experiencesSection = document.getElementById('experiencesSection');
    
    if (!experiencesGrid || !experiences) {
        if (experiencesSection) experiencesSection.style.display = 'none';
        return;
    }
    
    experiencesGrid.innerHTML = '';
    
    const categories = [
        { key: 'tours', icon: '🚶', title: 'Guided Tours' },
        { key: 'excursions', icon: '🚌', title: 'Day Excursions' },
        { key: 'must_see', icon: '⭐', title: 'Must-See Attractions' }
    ];
    
    let hasAnyExperiences = false;
    
    categories.forEach(cat => {
        const categoryData = experiences[cat.key];
        
        if (!categoryData || !categoryData.items || categoryData.items.length === 0) {
            console.log(`⚠️ No ${cat.key} found`);
            return;
        }
        
        hasAnyExperiences = true;
        
        const categoryDiv = document.createElement('div');
        categoryDiv.className = 'experience-category';
        
        let itemsHTML = categoryData.items.slice(0, 5).map(item => {
            const name = item.name || item;
            const description = item.description || '';
            const price = item.price || item.estimated_cost;
            const rating = item.rating;
            const photo = item.photo_url;
            const mapsLink = item.maps_link;
            
            const clickHandler = mapsLink ? `onclick="window.open('${mapsLink}', '_blank')"` : '';
            const cursorStyle = mapsLink ? 'cursor: pointer;' : '';
            
            return `
                <div class="experience-item" ${clickHandler} style="${cursorStyle}">
                    ${photo ? `<img src="${photo}" alt="${name}" onerror="this.style.display='none'">` : 
                             `<div class="experience-placeholder">${cat.icon}</div>`}
                    <div class="experience-item-info">
                        <div class="experience-item-name">${name}</div>
                        ${description ? `<div class="experience-item-desc">${description}</div>` : ''}
                        <div class="experience-item-meta">
                            ${rating ? `<span>⭐ ${rating}</span>` : ''}
                            ${price ? `<span class="experience-item-price">$${price}</span>` : ''}
                            ${mapsLink ? `<span style="color: #667eea; font-size: 11px;">📍 View on Map</span>` : ''}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        categoryDiv.innerHTML = `
            <h3>${cat.icon} ${categoryData.title || cat.title}</h3>
            <p>${categoryData.description || ''}</p>
            ${itemsHTML}
            ${categoryData.count > 5 ? `<div class="more-experiences">+${categoryData.count - 5} more available</div>` : ''}
        `;
        
        experiencesGrid.appendChild(categoryDiv);
    });
    
    experiencesSection.style.display = hasAnyExperiences ? 'block' : 'none';
    console.log(`🎭 Rendered experiences: tours=${experiences.tours?.items?.length || 0}, excursions=${experiences.excursions?.items?.length || 0}, must_see=${experiences.must_see?.items?.length || 0}`);
}

function renderFlightRecommendations(flights) {
    const section = document.getElementById('flightRecommendationsSection');
    const carousel = document.getElementById('flightCarousel');
    
    if (!flights || flights.length === 0) {
        // Show "No flights found" message
        section.style.display = 'block';
        carousel.innerHTML = `
            <div class="no-flights-card">
                <div class="no-flights-icon">✈️</div>
                <h3>No Flights Found</h3>
                <p>We couldn't find flights for this route. This may be because:</p>
                <ul style="text-align: left; margin: 15px auto; max-width: 400px;">
                    <li>This is a domestic trip without international flights</li>
                    <li>The route requires specific departure location</li>
                    <li>Limited flight availability to this destination</li>
                </ul>
                <p style="font-size: 14px; color: #666; margin-top: 15px;">
                    You may need to arrange flights separately or specify your departure city.
                </p>
            </div>
        `;
        return;
    }
    
    section.style.display = 'block';
    carousel.innerHTML = '';
    
    console.log(`✈️ Rendering ${flights.length} flight recommendations`);
    
    flights.forEach(flight => {
        const flightCard = document.createElement('div');
        flightCard.className = 'flight-card';
        flightCard.onclick = () => {
            if (flight.affiliate_link) {
                window.open(flight.affiliate_link, '_blank');
            }
        };
        
        flightCard.innerHTML = `
            <div class="airline-header">
                <img src="${flight.airline_logo || '/static/images/default-airline.png'}" 
                     alt="${flight.airline}" 
                     class="airline-logo"
                     onerror="this.src='/static/images/default-airline.png'">
                <div class="airline-info">
                    <h4>${flight.airline || 'Airline'}</h4>
                    <div class="flight-number">${flight.flight_number || 'N/A'}</div>
                </div>
            </div>
            
            <div class="flight-route">
                <div class="route-point">
                    <div class="route-code">${flight.origin_city || 'DEP'}</div>
                    <div class="route-time">${flight.departure_time || '10:00 AM'}</div>
                </div>
                <div class="route-arrow">
                    ✈️
                    <div style="font-size: 12px; color: #718096;">${flight.duration || '10h'}</div>
                </div>
                <div class="route-point">
                    <div class="route-code">${flight.destination_city || 'ARR'}</div>
                    <div class="route-time">${flight.arrival_time || '11:45 PM'}</div>
                </div>
            </div>
            
            <div class="flight-details">
                <div class="flight-info">
                    <span class="stops-badge">${flight.stops_text || 'Direct'}</span>
                    <span>${flight.class || 'Economy'}</span>
                </div>
                <div class="flight-price">
                    $${flight.price?.toLocaleString() || '0'}
                    <span class="per-person">/person</span>
                </div>
            </div>
        `;
        
        carousel.appendChild(flightCard);
    });
    
    console.log('✅ Flight recommendations rendered');
}

function renderHotelRecommendations(hotels) {
    const section = document.getElementById('hotelRecommendationsSection');
    const carousel = document.getElementById('hotelCarousel');
    
    if (!hotels || hotels.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    section.style.display = 'block';
    carousel.innerHTML = '';
    
    console.log(`🏨 Rendering ${hotels.length} hotel recommendations`);
    
    hotels.forEach(hotel => {
        const hotelCard = document.createElement('div');
        hotelCard.className = 'hotel-card';
        
        if (hotel.maps_link) {
            hotelCard.style.cursor = 'pointer';
            hotelCard.onclick = () => window.open(hotel.maps_link, '_blank');
        }
        
        const categoryColors = {
            'budget': { bg: '#dbeafe', color: '#1e40af' },
            'mid_range': { bg: '#fef3c7', color: '#92400e' },
            'luxury': { bg: '#fce7f3', color: '#831843' }
        };
        
        const catStyle = categoryColors[hotel.category] || categoryColors['mid_range'];
        
        hotelCard.innerHTML = `
            ${hotel.photo_url ? 
                `<img src="${hotel.photo_url}" alt="${hotel.name}" class="hotel-image" onerror="this.src='/static/images/default-hotel.jpg'">` :
                `<div class="hotel-image" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 48px;">🏨</div>`
            }
            <div class="hotel-content">
                <div class="hotel-name">${hotel.name}</div>
                <div class="hotel-rating">
                    <span class="rating-stars">${'⭐'.repeat(Math.round(hotel.rating || 4))}</span>
                    <span class="rating-count">${hotel.rating || '4.0'} (${hotel.user_ratings_total || 0} reviews)</span>
                </div>
                <div class="hotel-price-row">
                    <div class="hotel-price">
                        $${Math.round(hotel.price_per_night || 100)}
                        <span class="price-label">/night</span>
                    </div>
                    <span class="hotel-category" style="background: ${catStyle.bg}; color: ${catStyle.color}">
                        ${hotel.category?.replace('_', ' ') || 'Standard'}
                    </span>
                </div>
                ${hotel.maps_link ? `<div style="text-align: center; margin-top: 10px; color: #667eea; font-size: 12px;">📍 Click to view on map</div>` : ''}
            </div>
        `;
        
        carousel.appendChild(hotelCard);
    });
    
    console.log('✅ Hotel recommendations rendered');
}

function renderRestaurantRecommendations(restaurants) {
    const section = document.getElementById('restaurantRecommendationsSection');
    const carousel = document.getElementById('restaurantCarousel');
    
    if (!restaurants || restaurants.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    section.style.display = 'block';
    carousel.innerHTML = '';
    
    console.log(`🍽️ Rendering ${restaurants.length} restaurant recommendations`);
    
    restaurants.forEach(restaurant => {
        const restaurantCard = document.createElement('div');
        restaurantCard.className = 'restaurant-card';
        
        if (restaurant.maps_link) {
            restaurantCard.style.cursor = 'pointer';
            restaurantCard.onclick = () => window.open(restaurant.maps_link, '_blank');
        }
        
        restaurantCard.innerHTML = `
            ${restaurant.photo_url ? 
                `<img src="${restaurant.photo_url}" alt="${restaurant.name}" class="restaurant-image" onerror="this.src='/static/images/default-restaurant.jpg'">` :
                `<div class="restaurant-image" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); display: flex; align-items: center; justify-content: center; color: white; font-size: 48px;">🍽️</div>`
            }
            <div class="restaurant-content">
                <div class="restaurant-name">${restaurant.name}</div>
                <span class="cuisine-badge">${restaurant.cuisine || 'International'}</span>
                <div class="restaurant-rating">
                    <span class="rating-stars">${'⭐'.repeat(Math.round(restaurant.rating || 4))}</span>
                    <span class="rating-count">${restaurant.rating || '4.0'}</span>
                </div>
                <div class="restaurant-price-row">
                    <div class="restaurant-price">
                        $${Math.round(restaurant.avg_price || 25)}
                        <span class="price-label">/person</span>
                    </div>
                    <div class="price-range">
                        ${Array.from({length: 4}, (_, i) => 
                            `<span class="price-symbol ${i < (restaurant.price_level || 2) ? '' : 'inactive'}">$</span>`
                        ).join('')}
                    </div>
                </div>
                ${restaurant.maps_link ? `<div style="text-align: center; margin-top: 10px; color: #667eea; font-size: 12px;">📍 Click to view on map</div>` : ''}
            </div>
        `;
        
        carousel.appendChild(restaurantCard);
    });
    
    console.log('✅ Restaurant recommendations rendered');
}

function scrollCarousel(carouselId, direction) {
    const carousel = document.getElementById(carouselId);
    const scrollAmount = 340;
    carousel.scrollBy({
        left: direction * scrollAmount,
        behavior: 'smooth'
    });
}

// ============================================================================
// BUDGET BREAKDOWN - ITEMIZED WITH CLICKABLE DETAILS
// ============================================================================

function renderBudgetBreakdown(budgetBreakdown, totalBudget) {
    console.log('💰 Rendering ITEMIZED budget breakdown:', budgetBreakdown);
    
    const categories = budgetBreakdown.categories || {};
    const detailedItems = budgetBreakdown.detailed_items || {};
    
    // Update summary amounts (don't show contingency as allocated)
    document.getElementById('summaryFlights').textContent = `$${Math.round(categories.flights?.amount || 0).toLocaleString()}`;
    document.getElementById('summaryHotels').textContent = `$${Math.round(categories.hotels?.amount || 0).toLocaleString()}`;
    document.getElementById('summaryActivities').textContent = `$${Math.round(categories.activities?.amount || 0).toLocaleString()}`;
    document.getElementById('summaryFood').textContent = `$${Math.round(categories.food?.amount || 0).toLocaleString()}`;
    document.getElementById('summaryTransport').textContent = `$${Math.round(categories.travel?.amount || 0).toLocaleString()}`;
    
    // Contingency shows suggested amount (not allocated)
    const suggestedContingency = categories.contingency?.suggested_amount || 0;
    document.getElementById('summaryContingency').textContent = `$${Math.round(suggestedContingency).toLocaleString()} (suggested)`;
    
    // Update totals
    document.getElementById('totalEstimation').textContent = `$${Math.round(budgetBreakdown.total_allocated || 0).toLocaleString()}`;
    
    const remainingAmount = budgetBreakdown.remaining_budget || 0;
    const remainingElement = document.getElementById('remainingBudget');
    remainingElement.textContent = `$${Math.round(remainingAmount).toLocaleString()}`;
    
    // Style remaining budget prominently
    if (remainingAmount > 0) {
        remainingElement.style.color = '#10b981';
        remainingElement.style.fontWeight = '700';
        remainingElement.style.fontSize = '24px';
    }
    
    // Show/hide reallocation section
    const reallocationSection = document.getElementById('reallocationSection');
    if (remainingAmount > 10) {
        reallocationSection.style.display = 'block';
    } else {
        reallocationSection.style.display = 'none';
    }
    
    // Render detailed breakdowns
    renderFlightsBreakdown(detailedItems.flights || []);
    renderHotelsBreakdown(detailedItems.hotels || []);
    renderActivitiesBreakdown(
        detailedItems.must_do_activities || [], 
        detailedItems.recommended_activities || [], 
        detailedItems.optional_activities || [], 
        categories.activities || {}
    );
    renderFoodBreakdown(detailedItems.food || []);
    renderTransportBreakdown(detailedItems.travel || []);
    renderContingencyBreakdown(detailedItems.contingency || [], categories.contingency || {});
    
    // Update chart (exclude contingency from pie chart)
    const ctx = document.getElementById('budgetChart');
    if (!ctx) return;
    
    const chartContext = ctx.getContext('2d');
    
    if (budgetChart) {
        budgetChart.destroy();
    }
    
    budgetChart = new Chart(chartContext, {
        type: 'doughnut',
        data: {
            labels: ['Flights', 'Hotels', 'Activities', 'Food', 'Transport', 'Remaining'],
            datasets: [{
                data: [
                    categories.flights?.percentage || 0,
                    categories.hotels?.percentage || 0,
                    categories.activities?.percentage || 0,
                    categories.food?.percentage || 0,
                    categories.travel?.percentage || 0,
                    budgetBreakdown.remaining_percentage || 0
                ],
                backgroundColor: [
                    '#3b82f6',
                    '#8b5cf6',
                    '#ec4899',
                    '#10b981',
                    '#f59e0b',
                    '#22c55e'
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
                            return context.label + ': ' + context.parsed.toFixed(1) + '%';
                        }
                    }
                }
            }
        }
    });
    
    // Add click handlers to summary rows
    const summaryRows = document.querySelectorAll('.budget-summary-row');
    summaryRows.forEach((row, index) => {
        row.style.cursor = 'pointer';
        
        const newRow = row.cloneNode(true);
        row.parentNode.replaceChild(newRow, row);
        
        newRow.addEventListener('click', function() {
            console.log(`Clicked category index: ${index}`);
            toggleBreakdownSection(index);
            newRow.classList.toggle('active');
        });
    });
    
    console.log('✅ Budget breakdown rendered with itemized details');
}

function renderContingencyBreakdown(contingencyItems, contingencyCategory) {
    const section = document.getElementById('contingencyBreakdownSection');
    const content = document.getElementById('contingencyBreakdownContent');
    
    if (!contingencyItems || contingencyItems.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    const suggestedAmount = contingencyCategory.suggested_amount || 0;
    const suggestedPercentage = contingencyCategory.suggested_percentage || 7.5;
    const note = contingencyCategory.note || "Reserve 5-10% of your total budget for unexpected costs";
    
    let html = `
        <div style="background: #fef3c7; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
            <div style="font-weight: 700; color: #92400e; margin-bottom: 8px;">
                💡 Recommended Contingency Buffer
            </div>
            <div style="font-size: 14px; color: #78350f; margin-bottom: 8px;">
                ${note}
            </div>
            <div style="font-size: 20px; font-weight: 700; color: #92400e;">
                $${Math.round(suggestedAmount).toLocaleString()} (${suggestedPercentage}% of total budget)
            </div>
        </div>
        
        <p style="margin-bottom: 15px; color: #4b5563;">
            Below are typical unexpected expenses. Set aside funds from your remaining budget to cover these:
        </p>
        
        <table class="contingency-table">
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Estimated</th>
                    <th>How to Minimize</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    contingencyItems.forEach(item => {
        html += `
            <tr>
                <td><strong>${item.category}</strong></td>
                <td>$${item.estimated}</td>
                <td class="how-to-minimize">${item.detail}</td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
        
        <div style="margin-top: 15px; padding: 12px; background: #e0f2fe; border-radius: 8px;">
            <strong style="color: #0c4a6e;">💡 Pro Tip:</strong>
            <span style="color: #075985; font-size: 14px;">
                Use your remaining budget below to create your contingency fund, or reallocate it to other categories.
            </span>
        </div>
    `;
    
    content.innerHTML = html;
}

function toggleBreakdownSection(index) {
    console.log(`🔄 Toggling section ${index}`);
    
    const sectionMappings = [
        ['flightsBreakdownSection'],
        ['hotelsBreakdownSection'],
        ['mustDoBreakdownSection', 'recommendedBreakdownSection', 'optionalBreakdownSection'], // Activities
        ['foodBreakdownSection'],
        ['transportBreakdownSection'],
        ['contingencyBreakdownSection']
    ];
    
    const sectionIds = sectionMappings[index];
    
    if (!sectionIds) {
        console.error(`❌ No sections found for index ${index}`);
        return;
    }
    
    // Get first section to check current state
    const firstSection = document.getElementById(sectionIds[0]);
    if (!firstSection) {
        console.error(`❌ Section ${sectionIds[0]} not found`);
        return;
    }
    
    const isCurrentlyVisible = firstSection.style.display === 'block';
    console.log(`Current state: ${isCurrentlyVisible ? 'visible' : 'hidden'}`);
    
    // Toggle all related sections
    sectionIds.forEach(sectionId => {
        const section = document.getElementById(sectionId);
        if (section) {
            section.style.display = isCurrentlyVisible ? 'none' : 'block';
            console.log(`${sectionId}: ${isCurrentlyVisible ? 'hidden' : 'shown'}`);
        }
    });
}

function renderFlightsBreakdown(flights) {
    const section = document.getElementById('flightsBreakdownSection');
    const content = document.getElementById('flightsBreakdownContent');
    
    if (!flights || flights.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    let html = '';
    flights.forEach(flight => {
        html += `
            <div class="breakdown-item">
                <div class="breakdown-item-info">
                    <div class="breakdown-item-name">${flight.item}</div>
                    <div class="breakdown-item-detail">${flight.quantity} traveler(s) × $${flight.unit_price.toLocaleString()}/person</div>
                </div>
                <div class="breakdown-item-cost">
                    $${flight.total.toLocaleString()}
                    <span class="breakdown-item-badge badge-must">${flight.essential}</span>
                </div>
            </div>
        `;
    });
    
    content.innerHTML = html;
}

function renderHotelsBreakdown(hotels) {
    const section = document.getElementById('hotelsBreakdownSection');
    const content = document.getElementById('hotelsBreakdownContent');
    
    if (!hotels || hotels.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    let html = '';
    hotels.forEach(hotel => {
        html += `
            <div class="breakdown-item">
                <div class="breakdown-item-info">
                    <div class="breakdown-item-name">${hotel.item}</div>
                    <div class="breakdown-item-detail">${hotel.quantity}</div>
                </div>
                <div class="breakdown-item-cost">
                    $${hotel.total.toLocaleString()}
                    <span class="breakdown-item-badge badge-must">${hotel.essential}</span>
                </div>
            </div>
        `;
    });
    
    content.innerHTML = html;
}

function renderActivitiesBreakdown(mustDo, recommended, optional, activityCat) {
    const mustDoSection = document.getElementById('mustDoBreakdownSection');
    const recommendedSection = document.getElementById('recommendedBreakdownSection');
    const optionalSection = document.getElementById('optionalBreakdownSection');
    
    // Must-Do Activities
    if (mustDo && mustDo.length > 0) {
        const content = document.getElementById('mustDoBreakdownContent');
        let html = '';
        
        mustDo.forEach(activity => {
            html += `
                <div class="breakdown-item">
                    <div class="breakdown-item-info">
                        <div class="breakdown-item-name">${activity.item}</div>
                        ${activity.location ? `<div class="breakdown-item-location">📍 ${activity.location}</div>` : ''}
                        <div class="breakdown-item-detail">${activity.duration || 'Duration varies'}</div>
                    </div>
                    <div class="breakdown-item-cost">
                        $${activity.cost.toLocaleString()}
                        <span class="breakdown-item-badge badge-must">${activity.essential}</span>
                    </div>
                </div>
            `;
        });
        
        content.innerHTML = html;
        document.getElementById('mustDoTotal').textContent = `$${activityCat.must_do_total?.toLocaleString() || '0'}`;
    } else {
        mustDoSection.style.display = 'none';
    }
    
    // Recommended Activities
    if (recommended && recommended.length > 0) {
        const content = document.getElementById('recommendedBreakdownContent');
        let html = '';
        
        recommended.forEach(activity => {
            html += `
                <div class="breakdown-item">
                    <div class="breakdown-item-info">
                        <div class="breakdown-item-name">${activity.item}</div>
                        ${activity.location ? `<div class="breakdown-item-location">📍 ${activity.location}</div>` : ''}
                        <div class="breakdown-item-detail">${activity.duration || 'Duration varies'}</div>
                    </div>
                    <div class="breakdown-item-cost">
                        $${activity.cost.toLocaleString()}
                        <span class="breakdown-item-badge badge-recommended">${activity.essential}</span>
                    </div>
                </div>
            `;
        });
        
        content.innerHTML = html;
        document.getElementById('recommendedTotal').textContent = `$${activityCat.recommended_total?.toLocaleString() || '0'}`;
    } else {
        recommendedSection.style.display = 'none';
    }
    
    // Optional Activities
    if (optional && optional.length > 0) {
        const content = document.getElementById('optionalBreakdownContent');
        let html = '';
        
        optional.forEach(activity => {
            html += `
                <div class="breakdown-item">
                    <div class="breakdown-item-info">
                        <div class="breakdown-item-name">${activity.item}</div>
                        ${activity.location ? `<div class="breakdown-item-location">📍 ${activity.location}</div>` : ''}
                        <div class="breakdown-item-detail">${activity.duration || 'Duration varies'}</div>
                    </div>
                    <div class="breakdown-item-cost">
                        $${activity.cost.toLocaleString()}
                        <span class="breakdown-item-badge badge-optional">${activity.essential}</span>
                    </div>
                </div>
            `;
        });
        
        content.innerHTML = html;
        document.getElementById('optionalTotal').textContent = `$${activityCat.optional_total?.toLocaleString() || '0'}`;
    } else {
        optionalSection.style.display = 'none';
    }
}

function renderFoodBreakdown(foodItems) {
    const section = document.getElementById('foodBreakdownSection');
    const content = document.getElementById('foodBreakdownContent');
    
    if (!foodItems || foodItems.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    let html = '';
    let total = 0;
    
    foodItems.forEach(item => {
        total += item.cost;
        html += `
            <div class="breakdown-item">
                <div class="breakdown-item-info">
                    <div class="breakdown-item-name">${item.item}</div>
                    <div class="breakdown-item-detail">${item.detail}</div>
                </div>
                <div class="breakdown-item-cost">$${Math.round(item.cost).toLocaleString()}</div>
            </div>
        `;
    });
    
    content.innerHTML = html;
    document.getElementById('foodTotal').textContent = `$${Math.round(total).toLocaleString()}`;
}

function renderTransportBreakdown(transportItems) {
    const section = document.getElementById('transportBreakdownSection');
    const content = document.getElementById('transportBreakdownContent');
    
    if (!transportItems || transportItems.length === 0) {
        section.style.display = 'none';
        return;
    }
    
    let html = '';
    let total = 0;
    
    transportItems.forEach(item => {
        total += item.cost;
        html += `
            <div class="breakdown-item">
                <div class="breakdown-item-info">
                    <div class="breakdown-item-name">${item.item}</div>
                    <div class="breakdown-item-detail">${item.detail}</div>
                </div>
                <div class="breakdown-item-cost">$${Math.round(item.cost).toLocaleString()}</div>
            </div>
        `;
    });
    
    content.innerHTML = html;
    document.getElementById('transportTotal').textContent = `$${Math.round(total).toLocaleString()}`;
}

// FIXED: Budget reallocation with proper UI updates
async function reallocateBudget() {
    const checkboxes = document.querySelectorAll('.reallocation-checkbox input[type="checkbox"]:checked');
    const selectedCategories = Array.from(checkboxes).map(cb => cb.value);
    
    if (selectedCategories.length === 0) {
        alert('Please select at least one category to reallocate budget to');
        return;
    }
    
    console.log('💰 Reallocating to categories:', selectedCategories);
    
    const loadingModal = document.getElementById('loadingModal');
    loadingModal.classList.add('show');
    document.getElementById('loadingText').textContent = 'Reallocating budget and regenerating breakdowns...';
    
    try {
        const response = await fetch('/api/reallocate-budget', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                selected_categories: selectedCategories
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Budget reallocated:', data.budget_breakdown);
            console.log('📊 Detailed items:', data.budget_breakdown.detailed_items);
            
            // Update current itinerary
            currentItinerary.budget_breakdown = data.budget_breakdown;
            
            // Hide ALL breakdown sections before re-rendering
            const allSections = [
                'flightsBreakdownSection',
                'hotelsBreakdownSection', 
                'mustDoBreakdownSection',
                'recommendedBreakdownSection',
                'optionalBreakdownSection',
                'foodBreakdownSection',
                'transportBreakdownSection',
                'contingencyBreakdownSection'
            ];
            
            allSections.forEach(sectionId => {
                const section = document.getElementById(sectionId);
                if (section) {
                    section.style.display = 'none';
                    console.log(`🔒 Hidden ${sectionId}`);
                }
            });
            
            // Remove all active states from summary rows
            document.querySelectorAll('.budget-summary-row').forEach(row => {
                row.classList.remove('active');
            });
            
            // Re-render complete budget breakdown
            renderBudgetBreakdown(data.budget_breakdown, currentItinerary.total_budget);
            
            // Force immediate re-render of all breakdown sections with new data
            const detailedItems = data.budget_breakdown.detailed_items || {};
            const categories = data.budget_breakdown.categories || {};
            
            console.log('🔄 Force rendering all breakdowns with new data...');
            
            // Flights
            if (detailedItems.flights) {
                renderFlightsBreakdown(detailedItems.flights);
                console.log('✅ Rendered flights:', detailedItems.flights.length, 'items');
            }
            
            // Hotels
            if (detailedItems.hotels) {
                renderHotelsBreakdown(detailedItems.hotels);
                console.log('✅ Rendered hotels:', detailedItems.hotels.length, 'items');
            }
            
            // Activities
            renderActivitiesBreakdown(
                detailedItems.must_do_activities || [],
                detailedItems.recommended_activities || [],
                detailedItems.optional_activities || [],
                categories.activities || {}
            );
            console.log('✅ Rendered activities:',
                (detailedItems.must_do_activities?.length || 0), 'must-do,',
                (detailedItems.recommended_activities?.length || 0), 'recommended,',
                (detailedItems.optional_activities?.length || 0), 'optional'
            );
            
            // Food
            if (detailedItems.food) {
                renderFoodBreakdown(detailedItems.food);
                console.log('✅ Rendered food:', detailedItems.food.length, 'items');
            }
            
            // Transport
            if (detailedItems.travel) {
                renderTransportBreakdown(detailedItems.travel);
                console.log('✅ Rendered transport:', detailedItems.travel.length, 'items');
            }
            
            // Contingency
            if (detailedItems.contingency) {
                renderContingencyBreakdown(
                    detailedItems.contingency,
                    categories.contingency || {}
                );
                console.log('✅ Rendered contingency:', detailedItems.contingency.length, 'items');
            }
            
            // Destroy and recreate pie chart
            if (budgetChart) {
                budgetChart.destroy();
                console.log('🗑️ Destroyed old chart');
            }
            
            const ctx = document.getElementById('budgetChart');
            if (ctx) {
                budgetChart = new Chart(ctx.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: ['Flights', 'Hotels', 'Activities', 'Food', 'Transport', 'Remaining'],
                        datasets: [{
                            data: [
                                categories.flights?.percentage || 0,
                                categories.hotels?.percentage || 0,
                                categories.activities?.percentage || 0,
                                categories.food?.percentage || 0,
                                categories.travel?.percentage || 0,
                                data.budget_breakdown.remaining_percentage || 0
                            ],
                            backgroundColor: [
                                '#3b82f6',
                                '#8b5cf6',
                                '#ec4899',
                                '#10b981',
                                '#f59e0b',
                                '#22c55e'
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
                                        return context.label + ': ' + context.parsed.toFixed(1) + '%';
                                    }
                                }
                            }
                        }
                    }
                });
                console.log('📊 Created new chart with updated data');
            }
            
            // Uncheck all checkboxes
            checkboxes.forEach(cb => cb.checked = false);
            
            console.log('✅ Budget reallocation complete - all breakdowns updated!');
            
            // Show success message
            const successMsg = document.createElement('div');
            successMsg.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #10b981; color: white; padding: 15px 20px; border-radius: 8px; font-weight: 600; z-index: 10000; animation: slideIn 0.3s ease; box-shadow: 0 4px 6px rgba(0,0,0,0.1);';
            successMsg.innerHTML = `
                <div>✅ Budget reallocated successfully!</div>
                <div style="font-size: 12px; margin-top: 5px; opacity: 0.9;">
                    Click category rows above to view updated breakdowns
                </div>
            `;
            document.body.appendChild(successMsg);
            
            setTimeout(() => {
                successMsg.style.animation = 'slideOut 0.3s ease';
                setTimeout(() => successMsg.remove(), 300);
            }, 4000);
            
        } else {
            throw new Error(data.error || 'Failed to reallocate budget');
        }
    } catch (error) {
        console.error('❌ Error:', error);
        alert('An error occurred while reallocating budget: ' + error.message);
    } finally {
        loadingModal.classList.remove('show');
    }
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(400px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(400px); opacity: 0; }
    }
`;
document.head.appendChild(style);

// ============================================================================
// REMAINING FUNCTIONS (Attractions, Chat, PDF, etc.)
// ============================================================================

function renderAttractionsAndActivities(summary) {
    if (!summary) return;
    
    console.log('🎭 Rendering attractions and activities:', summary);
    
    const attractionsDescription = document.getElementById('attractionsDescription');
    const attractionsList = document.getElementById('attractionsList');
    const attractionImagesGrid = document.getElementById('attractionImagesGrid');
    
    if (attractionsDescription && attractionsList && summary.attractions) {
        attractionsDescription.textContent = summary.attractions.description || '';
        
        const items = summary.attractions.items || [];
        attractionsList.innerHTML = items.map(item => `<li>${item}</li>`).join('');
        
        const photos = summary.attractions.photos?.filter(p => p && p !== 'null') || [];
        if (photos.length > 0 && attractionImagesGrid) {
            attractionImagesGrid.innerHTML = photos.slice(0, 4).map(photo => 
                `<img src="${photo}" alt="Attraction" onerror="this.style.display='none'">`
            ).join('');
        }
    }
    
    const activitiesDescription = document.getElementById('activitiesDescription');
    const activitiesList = document.getElementById('activitiesList');
    const activityImagesGrid = document.getElementById('activityImagesGrid');
    
    if (activitiesDescription && activitiesList && summary.activities) {
        activitiesDescription.textContent = summary.activities.description || '';
        
        const items = summary.activities.items || [];
        activitiesList.innerHTML = items.map(item => `<li>${item}</li>`).join('');
        
        const photos = summary.activities.photos?.filter(p => p && p !== 'null') || [];
        if (photos.length > 0 && activityImagesGrid) {
            activityImagesGrid.innerHTML = photos.slice(0, 4).map(photo => 
                `<img src="${photo}" alt="Activity" onerror="this.style.display='none'">`
            ).join('');
        }
    }
}

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
            
            const preview = document.getElementById('uploadPreview');
            preview.src = data.url;
            preview.style.display = 'block';
            
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

async function generateVideo() {
    if (!uploadedPhotoFilename) {
        alert('Please upload your photo first!');
        return;
    }
    
    console.log('🎥 Starting video generation...');
    
    const loadingModal = document.getElementById('loadingModal');
    loadingModal.classList.add('show');
    document.getElementById('loadingText').textContent = 'Generating your travel video...';
    
    try {
        const response = await fetch('/api/generate-video', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                itinerary_id: itineraryId,
                user_photo_filename: uploadedPhotoFilename
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            console.log('✅ Video generation started:', data.video_id);
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

// Chat functionality
function toggleChat() {
    const chatWindow = document.getElementById('chatWindow');
    chatWindow.classList.toggle('show');
}

function minimizeChat() {
    document.getElementById('chatWindow').classList.remove('show');
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
    
    conversationHistory.push({ role: 'user', content: message });
    
    const loadingId = addLoadingMessage();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
            conversationHistory.push({ role: 'assistant', content: data.response });
            
            if (data.requires_confirmation && data.proposed_changes) {
                pendingChanges = data.proposed_changes;
                showConfirmationButtons();
            }
            
            if (data.modifications_made && data.updated_itinerary) {
                console.log('🔄 Updating itinerary from chat');
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
            <button class="btn-confirm" onclick="confirmChanges()">✅ Yes, Apply</button>
            <button class="btn-cancel" onclick="cancelChanges()">❌ Cancel</button>
        </div>
    `;
    chatMessages.appendChild(buttonsDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function confirmChanges() {
    if (!pendingChanges) return;
    
    addMessageToChat('user', 'Yes, please apply the changes');
    conversationHistory.push({ role: 'user', content: 'Yes, please apply the changes' });
    
    const buttons = document.querySelector('.confirmation-buttons');
    if (buttons) buttons.remove();
    
    const loadingId = addLoadingMessage();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
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
            conversationHistory.push({ role: 'assistant', content: data.response });
            
            if (data.modifications_made && data.updated_itinerary) {
                console.log('🔄 Applying confirmed changes');
                currentItinerary = data.updated_itinerary;
                renderItinerary(currentItinerary);
                
                setTimeout(() => {
                    addMessageToChat('bot', '✅ Changes applied! Scroll up to see your updated itinerary.');
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
    conversationHistory.push({ role: 'user', content: 'No, cancel the changes' });
    
    addMessageToChat('bot', 'Okay, cancelled. What else would you like to do?');
    conversationHistory.push({ role: 'assistant', content: 'Okay, cancelled.' });
    
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

async function downloadItineraryAsPDF() {
    const button = document.getElementById('downloadPdfBtn');
    const originalText = button.innerHTML;
    
    button.disabled = true;
    button.innerHTML = '<span class="download-icon">⏳</span><span>Generating PDF...</span>';
    
    try {
        console.log('📄 Starting PDF generation...');
        
        const element = document.getElementById('itineraryContent');
        document.body.classList.add('pdf-generating');
        
        const destination = currentItinerary?.destination?.name || 'Itinerary';
        const sanitizedDestination = destination.replace(/[^a-z0-9]/gi, '_');
        const filename = `${sanitizedDestination}_Travel_Itinerary.pdf`;
        
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
        
        await html2pdf().set(opt).from(element).save();
        
        console.log('✅ PDF generated successfully!');
        
        button.innerHTML = '<span class="download-icon">✅</span><span>Downloaded!</span>';
        
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText;
            document.body.classList.remove('pdf-generating');
        }, 2000);
        
    } catch (error) {
        console.error('❌ Error generating PDF:', error);
        
        button.innerHTML = '<span class="download-icon">❌</span><span>Error! Try Again</span>';
        
        setTimeout(() => {
            button.disabled = false;
            button.innerHTML = originalText;
            document.body.classList.remove('pdf-generating');
        }, 2000);
        
        alert('Failed to generate PDF. Please try again.');
    }
}

console.log('✅ Itinerary.js loaded - v5.0 FIXED budget reallocation with proper UI updates');
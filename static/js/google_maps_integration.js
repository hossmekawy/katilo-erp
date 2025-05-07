/**
 * Google Maps Integration for Katilo Sales Representative Management
 *
 * This file contains functions for integrating Google Maps with the sales representative
 * management system, including route planning, tracking, and visualization.
 */

// Global variables
let map;
let directionsService;
let directionsRenderer;
let geocoder;
let markers = [];
let currentInfoWindow = null;
let watchPositionId = null;
let representativeMarkers = {};

/**
 * Initialize the Google Maps API
 * @param {string} containerId - The ID of the container element for the map
 * @param {Object} options - Map initialization options
 * @param {Object} options.center - The center coordinates {lat, lng}
 * @param {number} options.zoom - The zoom level
 * @param {boolean} options.directions - Whether to initialize directions service
 * @param {boolean} options.geocoding - Whether to initialize geocoding service
 */
function initMap(containerId, options = {}) {
    try {
        // Check if Google Maps API is loaded
        if (typeof google === 'undefined' || typeof google.maps === 'undefined') {
            console.error('Google Maps API not loaded. Please check your API key and connection.');

            // Display error message in the map container
            const container = document.getElementById(containerId);
            if (container) {
                container.innerHTML = '<div class="p-4 bg-red-100 text-red-700 rounded-lg">' +
                    '<p class="font-bold">خطأ في تحميل خرائط جوجل</p>' +
                    '<p>يرجى التحقق من اتصالك بالإنترنت وإعادة تحميل الصفحة.</p>' +
                    '</div>';
            }

            return null;
        }

        // Default options
        const defaultOptions = {
            center: { lat: 30.0444, lng: 31.2357 }, // Cairo, Egypt as default
            zoom: 10,
            directions: false,
            geocoding: false
        };

        // Merge options
        const mapOptions = {...defaultOptions, ...options };

        // Get the container element
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`Map container element with ID "${containerId}" not found.`);
            return null;
        }

        // Initialize the map with enhanced features for sales representative management
        map = new google.maps.Map(container, {
            center: mapOptions.center,
            zoom: mapOptions.zoom,
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: true,
            streetViewControl: true,
            fullscreenControl: true,
        });

        // Initialize directions service if requested
        if (mapOptions.directions) {
            directionsService = new google.maps.DirectionsService();
            directionsRenderer = new google.maps.DirectionsRenderer({
                map: map,
                suppressMarkers: false,
                preserveViewport: false,
                polylineOptions: {
                    strokeColor: '#4285F4',
                    strokeWeight: 5,
                    strokeOpacity: 0.8
                }
            });
        }

        // Initialize geocoding service if requested
        if (mapOptions.geocoding) {
            geocoder = new google.maps.Geocoder();
        }

        return map;
    } catch (error) {
        console.error('Error initializing Google Maps:', error);

        // Display error message in the map container
        const container = document.getElementById(containerId);
        if (container) {
            container.innerHTML = '<div class="p-4 bg-red-100 text-red-700 rounded-lg">' +
                '<p class="font-bold">خطأ في تهيئة خرائط جوجل</p>' +
                '<p>يرجى التحقق من اتصالك بالإنترنت وإعادة تحميل الصفحة.</p>' +
                '<p class="text-sm mt-2">تفاصيل الخطأ: ' + error.message + '</p>' +
                '</div>';
        }

        return null;
    }
}

/**
 * Add a marker to the map
 * @param {Object} position - The position {lat, lng}
 * @param {string} title - The marker title
 * @param {string} icon - URL to a custom icon (optional)
 * @param {string} content - Content for the info window (optional)
 * @param {Object} options - Additional marker options
 * @returns {Object} - The created marker
 */
function addMarker(position, title, icon = null, content = null, options = {}) {
    try {
        // Check if position is valid
        if (!position || typeof position.lat !== 'number' || typeof position.lng !== 'number') {
            console.error('Invalid position for marker:', position);
            return null;
        }

        // Check if map is initialized
        if (!map) {
            console.error('Map not initialized');
            return null;
        }

        // Always try to use AdvancedMarkerElement first
        if (google.maps.marker && google.maps.marker.AdvancedMarkerElement) {
            // Create marker content
            const markerContent = document.createElement('div');

            if (options.label) {
                // Create a pin with a label
                markerContent.innerHTML = `
                    <div style="display: flex; align-items: center; justify-content: center;
                         background-color: ${options.fillColor || '#4285F4'};
                         color: white; font-weight: bold; font-size: 12px;
                         border-radius: 50%; width: 24px; height: 24px;
                         border: 2px solid white;">
                        ${options.label}
                    </div>
                `;
            } else if (icon) {
                // Use custom icon
                if (typeof icon === 'string') {
                    // Icon is a URL
                    const img = document.createElement('img');
                    img.src = icon;
                    img.style.width = '24px';
                    img.style.height = '24px';
                    markerContent.appendChild(img);
                } else {
                    // Icon is a complex object (like a symbol)
                    markerContent.innerHTML = `
                        <div style="background-color: ${icon.fillColor || '#4285F4'};
                             border-radius: 50%; width: ${icon.scale || 10}px;
                             height: ${icon.scale || 10}px;
                             border: 2px solid ${icon.strokeColor || 'white'};"></div>
                    `;
                }
            } else {
                // Default marker appearance
                markerContent.innerHTML = '<div style="background-color: #4285F4; border-radius: 50%; width: 24px; height: 24px; border: 2px solid white;"></div>';
            }

            // Create advanced marker
            const marker = new google.maps.marker.AdvancedMarkerElement({
                position: position,
                map: map,
                title: title,
                content: markerContent,
                ...options
            });

            markers.push(marker);

            if (content) {
                const infoWindow = new google.maps.InfoWindow({
                    content: content
                });

                // Use the proper event listener for AdvancedMarkerElement
                marker.addEventListener('click', function() {
                    if (currentInfoWindow) {
                        currentInfoWindow.close();
                    }
                    infoWindow.open({
                        anchor: marker,
                        map: map
                    });
                    currentInfoWindow = infoWindow;
                });
            }

            return marker;
        } else {
            // Fall back to regular Marker if AdvancedMarkerElement is not available
            console.warn('AdvancedMarkerElement not available, falling back to Marker');

            const markerOptions = {
                position: position,
                map: map,
                title: title,
                animation: google.maps.Animation.DROP,
                ...options
            };

            if (icon) {
                markerOptions.icon = icon;
            }

            const marker = new google.maps.Marker(markerOptions);
            markers.push(marker);

            if (content) {
                const infoWindow = new google.maps.InfoWindow({
                    content: content
                });

                marker.addListener('click', function() {
                    if (currentInfoWindow) {
                        currentInfoWindow.close();
                    }
                    infoWindow.open(map, marker);
                    currentInfoWindow = infoWindow;
                });
            }

            return marker;
        }
    } catch (error) {
        console.error('Error adding marker:', error);
        return null;
    }
}

/**
 * Clear all markers from the map
 */
function clearMarkers() {
    for (let marker of markers) {
        try {
            // Handle both regular Marker and AdvancedMarkerElement
            if (marker instanceof google.maps.marker.AdvancedMarkerElement) {
                marker.map = null;
            } else if (marker.setMap) {
                marker.setMap(null);
            }
        } catch (error) {
            console.error('Error clearing marker:', error);
        }
    }
    markers = [];
}

/**
 * Calculate and display a route between two or more points
 * @param {Array} waypoints - Array of waypoint objects with location and stopover properties
 * @param {Object} origin - The starting point {lat, lng} or address string
 * @param {Object} destination - The ending point {lat, lng} or address string
 * @param {string} travelMode - The travel mode (DRIVING, WALKING, BICYCLING, TRANSIT)
 * @param {Function} callback - Callback function to handle the result
 * @param {Object} options - Additional options for route calculation
 */
function calculateRoute(waypoints, origin, destination, travelMode = 'DRIVING', callback, options = {}) {
    if (!directionsService || !directionsRenderer) {
        console.error('Directions service not initialized');
        return;
    }

    // Default options
    const defaultOptions = {
        trafficModel: 'bestguess', // Options: 'bestguess', 'optimistic', 'pessimistic'
        avoidHighways: false,
        avoidTolls: false,
        averageSpeed: 40, // km/h, used for custom time calculations
        departureTime: new Date() // Current time for traffic calculations
    };

    // Merge default options with provided options
    const routeOptions = {...defaultOptions, ...options };

    const request = {
        origin: origin,
        destination: destination,
        waypoints: waypoints,
        optimizeWaypoints: true,
        travelMode: google.maps.TravelMode[travelMode],
        drivingOptions: {
            departureTime: routeOptions.departureTime,
            trafficModel: google.maps.TrafficModel[routeOptions.trafficModel.toUpperCase()]
        },
        avoidHighways: routeOptions.avoidHighways,
        avoidTolls: routeOptions.avoidTolls
    };

    directionsService.route(request, function(result, status) {
        if (status === google.maps.DirectionsStatus.OK) {
            directionsRenderer.setDirections(result);

            // Calculate custom travel times based on average speed if provided
            if (routeOptions.averageSpeed > 0) {
                const route = result.routes[0];

                // Calculate total distance in kilometers
                let totalDistance = 0;
                route.legs.forEach(leg => {
                    totalDistance += leg.distance.value; // in meters
                });

                // Convert to kilometers
                totalDistance = totalDistance / 1000;

                // Calculate custom travel time in minutes based on average speed
                const customTravelTimeMinutes = Math.round((totalDistance / routeOptions.averageSpeed) * 60);

                // Add custom travel time to result
                result.customTravelTime = {
                    minutes: customTravelTimeMinutes,
                    text: `${customTravelTimeMinutes} دقيقة`,
                    basedOnSpeed: routeOptions.averageSpeed
                };

                // Add traffic-based travel times
                result.trafficTravelTime = {
                    bestGuess: getTotalDuration(route),
                    withTraffic: getTotalDurationWithTraffic(route)
                };
            }

            if (callback && typeof callback === 'function') {
                callback(result);
            }
        } else {
            console.error('Directions request failed due to ' + status);
        }
    });
}

/**
 * Get total duration of a route in minutes
 * @param {Object} route - The route object from Google Maps API
 * @returns {number} - Duration in minutes
 */
function getTotalDuration(route) {
    let totalDuration = 0;
    route.legs.forEach(leg => {
        totalDuration += leg.duration.value; // in seconds
    });
    return Math.round(totalDuration / 60); // convert to minutes
}

/**
 * Get total duration with traffic of a route in minutes
 * @param {Object} route - The route object from Google Maps API
 * @returns {number} - Duration in minutes
 */
function getTotalDurationWithTraffic(route) {
    let totalDuration = 0;
    route.legs.forEach(leg => {
        // Use duration_in_traffic if available, otherwise fall back to regular duration
        const legDuration = leg.duration_in_traffic ? leg.duration_in_traffic.value : leg.duration.value;
        totalDuration += legDuration; // in seconds
    });
    return Math.round(totalDuration / 60); // convert to minutes
}

/**
 * Geocode an address to coordinates
 * @param {string} address - The address to geocode
 * @param {Function} callback - Callback function to handle the result
 */
function geocodeAddress(address, callback) {
    if (!geocoder) {
        console.error('Geocoder not initialized');
        return;
    }

    geocoder.geocode({ 'address': address }, function(results, status) {
        if (status === google.maps.GeocoderStatus.OK) {
            if (callback && typeof callback === 'function') {
                callback(results[0].geometry.location, results[0]);
            }
        } else {
            console.error('Geocode was not successful for the following reason: ' + status);
        }
    });
}

/**
 * Start tracking a representative's location
 * @param {number} repId - The representative ID
 * @param {Function} updateCallback - Callback function to handle position updates
 */
function startTracking(repId, updateCallback) {
    if (navigator.geolocation) {
        watchPositionId = navigator.geolocation.watchPosition(
            function(position) {
                const pos = {
                    lat: position.coords.latitude,
                    lng: position.coords.longitude
                };

                // Update the representative's marker
                if (representativeMarkers[repId]) {
                    representativeMarkers[repId].setPosition(pos);
                } else {
                    const marker = addMarker(
                        pos,
                        'Current Location',
                        'https://maps.google.com/mapfiles/ms/icons/blue-dot.png',
                        '<div><strong>Current Location</strong></div>'
                    );
                    representativeMarkers[repId] = marker;
                }

                if (updateCallback && typeof updateCallback === 'function') {
                    updateCallback(pos, position);
                }
            },
            function(error) {
                console.error('Error getting location:', error);
            }, {
                enableHighAccuracy: true,
                timeout: 5000,
                maximumAge: 0
            }
        );
    } else {
        console.error('Geolocation is not supported by this browser.');
    }
}

/**
 * Stop tracking a representative's location
 */
function stopTracking() {
    if (watchPositionId !== null) {
        navigator.geolocation.clearWatch(watchPositionId);
        watchPositionId = null;
    }
}

/**
 * Update server with current location
 * @param {number} repId - The representative ID
 * @param {Object} position - The current position {lat, lng}
 * @param {number} routeId - The current route ID (optional)
 * @param {number} visitId - The current visit ID (optional)
 */
function updateLocationOnServer(repId, position, routeId = null, visitId = null) {
    const data = {
        representative_id: repId,
        latitude: position.lat,
        longitude: position.lng,
        timestamp: new Date().toISOString()
    };

    if (routeId) {
        data.route_id = routeId;
    }

    if (visitId) {
        data.visit_id = visitId;
    }

    fetch('/sales/representatives/tracking/update-location', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        })
        .then(response => response.json())
        .then(data => {
            console.log('Location updated successfully:', data);
        })
        .catch(error => {
            console.error('Error updating location:', error);
        });
}

/**
 * Calculate the optimal route for a set of customer visits
 * @param {Array} customers - Array of customer objects with location data
 * @param {Function} callback - Callback function to handle the optimized route
 */
function optimizeRoute(customers, callback) {
    if (customers.length < 2) {
        console.error('Need at least 2 customers to optimize a route');
        return;
    }

    const origin = customers[0].location;
    const destination = customers[customers.length - 1].location;
    const waypoints = customers.slice(1, -1).map(customer => ({
        location: customer.location,
        stopover: true
    }));

    calculateRoute(waypoints, origin, destination, 'DRIVING', function(result) {
        if (callback && typeof callback === 'function') {
            // Extract the optimized order of waypoints
            const waypointOrder = result.routes[0].waypoint_order;

            // Reorder customers based on the optimized waypoint order
            const optimizedCustomers = [customers[0]];

            for (let i = 0; i < waypointOrder.length; i++) {
                optimizedCustomers.push(customers[1 + waypointOrder[i]]);
            }

            optimizedCustomers.push(customers[customers.length - 1]);

            callback(optimizedCustomers, result);
        }
    });
}

/**
 * Create a heatmap of customer locations
 * @param {Array} customers - Array of customer objects with location data
 */
function createCustomerHeatmap(customers) {
    if (!google.maps.visualization) {
        console.error('Visualization library not loaded');
        return;
    }

    const heatmapData = customers.map(customer => {
        return new google.maps.LatLng(
            customer.location.lat,
            customer.location.lng
        );
    });

    const heatmap = new google.maps.visualization.HeatmapLayer({
        data: heatmapData,
        map: map,
        radius: 20
    });

    return heatmap;
}

/**
 * Calculate the distance and duration between two points
 * @param {Object} origin - The starting point {lat, lng} or address string
 * @param {Object} destination - The ending point {lat, lng} or address string
 * @param {string} travelMode - The travel mode (DRIVING, WALKING, BICYCLING, TRANSIT)
 * @param {Function} callback - Callback function to handle the result
 */
function calculateDistance(origin, destination, travelMode = 'DRIVING', callback) {
    if (!directionsService) {
        console.error('Directions service not initialized');
        return;
    }

    const request = {
        origin: origin,
        destination: destination,
        travelMode: google.maps.TravelMode[travelMode]
    };

    directionsService.route(request, function(result, status) {
        if (status === google.maps.DirectionsStatus.OK) {
            const route = result.routes[0];
            const leg = route.legs[0];

            const distance = leg.distance.text;
            const duration = leg.duration.text;

            if (callback && typeof callback === 'function') {
                callback({
                    distance: distance,
                    duration: duration,
                    distanceValue: leg.distance.value, // in meters
                    durationValue: leg.duration.value // in seconds
                });
            }
        } else {
            console.error('Distance calculation failed due to ' + status);
        }
    });
}
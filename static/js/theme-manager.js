/**
 * Theme Manager for Katilo System
 * Handles theme application, switching, and persistence for both base.html and base2.html
 */

// Initialize the theme manager
document.addEventListener('DOMContentLoaded', function() {
    // Apply theme from localStorage or server settings
    ThemeManager.initialize();
});

// Global Theme Manager
const ThemeManager = {
    // Current theme settings
    settings: {
        theme_mode: 'light',
        theme_color: 'blue',
        background_color: 'blue',
        sidebar_color: 'blue',
        font_family: 'Tajawal',
        font_size: 'medium',
        border_radius: 'medium',
        animation_speed: 'normal',
        layout_density: 'comfortable',
        sidebar_collapsed: false,
        rtl_enabled: true,
        custom_colors: {}
    },

    // CSS variables map
    cssVars: {
        // Theme mode variables
        'light': {
            '--bg-primary': '#ffffff',
            '--bg-secondary': '#f8fafc',
            '--text-primary': '#1e293b',
            '--text-secondary': '#64748b',
            '--border-color': '#e2e8f0'
        },
        'dark': {
            '--bg-primary': '#1e293b',
            '--bg-secondary': '#0f172a',
            '--text-primary': '#f8fafc',
            '--text-secondary': '#cbd5e1',
            '--border-color': '#334155'
        },
        // Font size variables
        'font-size': {
            'small': {
                '--text-xs': '0.7rem',
                '--text-sm': '0.8rem',
                '--text-base': '0.9rem',
                '--text-lg': '1rem',
                '--text-xl': '1.1rem',
                '--text-2xl': '1.2rem'
            },
            'medium': {
                '--text-xs': '0.75rem',
                '--text-sm': '0.875rem',
                '--text-base': '1rem',
                '--text-lg': '1.125rem',
                '--text-xl': '1.25rem',
                '--text-2xl': '1.5rem'
            },
            'large': {
                '--text-xs': '0.8rem',
                '--text-sm': '0.95rem',
                '--text-base': '1.1rem',
                '--text-lg': '1.25rem',
                '--text-xl': '1.4rem',
                '--text-2xl': '1.7rem'
            }
        },
        // Border radius variables
        'border-radius': {
            'small': {
                '--radius-sm': '0.125rem',
                '--radius-md': '0.25rem',
                '--radius-lg': '0.375rem',
                '--radius-xl': '0.5rem'
            },
            'medium': {
                '--radius-sm': '0.25rem',
                '--radius-md': '0.375rem',
                '--radius-lg': '0.5rem',
                '--radius-xl': '0.75rem'
            },
            'large': {
                '--radius-sm': '0.375rem',
                '--radius-md': '0.5rem',
                '--radius-lg': '0.75rem',
                '--radius-xl': '1rem'
            }
        },
        // Animation speed variables
        'animation-speed': {
            'slow': {
                '--transition-slow': '0.5s',
                '--transition-normal': '0.3s',
                '--transition-fast': '0.2s'
            },
            'normal': {
                '--transition-slow': '0.3s',
                '--transition-normal': '0.2s',
                '--transition-fast': '0.1s'
            },
            'fast': {
                '--transition-slow': '0.2s',
                '--transition-normal': '0.1s',
                '--transition-fast': '0.05s'
            },
            'none': {
                '--transition-slow': '0s',
                '--transition-normal': '0s',
                '--transition-fast': '0s'
            }
        },
        // Layout density variables
        'layout-density': {
            'compact': {
                '--spacing-xs': '0.25rem',
                '--spacing-sm': '0.5rem',
                '--spacing-md': '0.75rem',
                '--spacing-lg': '1rem',
                '--spacing-xl': '1.5rem'
            },
            'comfortable': {
                '--spacing-xs': '0.5rem',
                '--spacing-sm': '0.75rem',
                '--spacing-md': '1rem',
                '--spacing-lg': '1.5rem',
                '--spacing-xl': '2rem'
            },
            'spacious': {
                '--spacing-xs': '0.75rem',
                '--spacing-sm': '1rem',
                '--spacing-md': '1.5rem',
                '--spacing-lg': '2rem',
                '--spacing-xl': '3rem'
            }
        }
    },

    // Initialize theme manager
    initialize: function() {
        // Try to load settings from localStorage
        const savedSettings = localStorage.getItem('theme_settings');
        if (savedSettings) {
            try {
                const parsedSettings = JSON.parse(savedSettings);
                this.settings = { ...this.settings, ...parsedSettings };
            } catch (e) {
                console.error('Error parsing saved theme settings:', e);
            }
        }

        // Apply the theme
        this.applyTheme();

        // Set up event listeners for theme changes
        document.addEventListener('theme-changed', (e) => {
            if (e.detail && e.detail.settings) {
                this.updateTheme(e.detail.settings);
            }
        });
    },

    // Apply the current theme settings
    applyTheme: function() {
        // Apply theme mode (light/dark)
        this.applyThemeMode();

        // Apply font family
        document.documentElement.style.setProperty('--font-family', this.settings.font_family);

        // Apply font size
        this.applyFontSize();

        // Apply border radius
        this.applyBorderRadius();

        // Apply animation speed
        this.applyAnimationSpeed();

        // Apply layout density
        this.applyLayoutDensity();

        // Apply RTL direction
        this.applyRTL();

        // Apply custom colors
        this.applyCustomColors();

        // Apply sidebar state
        this.applySidebarState();

        // Save settings to localStorage
        localStorage.setItem('theme_settings', JSON.stringify(this.settings));
    },

    // Apply theme mode (light/dark)
    applyThemeMode: function() {
        const mode = this.settings.theme_mode;
        
        // Auto mode based on system preference
        if (mode === 'auto') {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            const themeVars = prefersDark ? this.cssVars['dark'] : this.cssVars['light'];
            
            // Apply CSS variables
            for (const [key, value] of Object.entries(themeVars)) {
                document.documentElement.style.setProperty(key, value);
            }
            
            // Add appropriate class to body
            if (prefersDark) {
                document.body.classList.add('dark');
                document.body.classList.remove('light');
            } else {
                document.body.classList.add('light');
                document.body.classList.remove('dark');
            }
        } else {
            // Apply specific mode
            const themeVars = this.cssVars[mode];
            
            // Apply CSS variables
            for (const [key, value] of Object.entries(themeVars)) {
                document.documentElement.style.setProperty(key, value);
            }
            
            // Add appropriate class to body
            document.body.classList.add(mode);
            document.body.classList.remove(mode === 'light' ? 'dark' : 'light');
        }
    },

    // Apply font size
    applyFontSize: function() {
        const size = this.settings.font_size;
        const fontSizeVars = this.cssVars['font-size'][size];
        
        // Apply CSS variables
        for (const [key, value] of Object.entries(fontSizeVars)) {
            document.documentElement.style.setProperty(key, value);
        }
    },

    // Apply border radius
    applyBorderRadius: function() {
        const radius = this.settings.border_radius;
        const radiusVars = this.cssVars['border-radius'][radius];
        
        // Apply CSS variables
        for (const [key, value] of Object.entries(radiusVars)) {
            document.documentElement.style.setProperty(key, value);
        }
    },

    // Apply animation speed
    applyAnimationSpeed: function() {
        const speed = this.settings.animation_speed;
        const speedVars = this.cssVars['animation-speed'][speed];
        
        // Apply CSS variables
        for (const [key, value] of Object.entries(speedVars)) {
            document.documentElement.style.setProperty(key, value);
        }
    },

    // Apply layout density
    applyLayoutDensity: function() {
        const density = this.settings.layout_density;
        const densityVars = this.cssVars['layout-density'][density];
        
        // Apply CSS variables
        for (const [key, value] of Object.entries(densityVars)) {
            document.documentElement.style.setProperty(key, value);
        }
    },

    // Apply RTL direction
    applyRTL: function() {
        const isRTL = this.settings.rtl_enabled;
        document.documentElement.dir = isRTL ? 'rtl' : 'ltr';
        document.documentElement.lang = isRTL ? 'ar' : 'en';
    },

    // Apply custom colors
    applyCustomColors: function() {
        const colors = this.settings.custom_colors;
        
        // Apply each custom color
        for (const [key, value] of Object.entries(colors)) {
            document.documentElement.style.setProperty(`--color-${key}`, value);
        }
    },

    // Apply sidebar state
    applySidebarState: function() {
        const isCollapsed = this.settings.sidebar_collapsed;
        
        // Find sidebar element
        const sidebar = document.querySelector('aside');
        if (sidebar) {
            if (isCollapsed) {
                sidebar.classList.add('collapsed');
            } else {
                sidebar.classList.remove('collapsed');
            }
        }
    },

    // Update theme with new settings
    updateTheme: function(newSettings) {
        // Update settings
        this.settings = { ...this.settings, ...newSettings };
        
        // Apply the updated theme
        this.applyTheme();
    },

    // Toggle theme mode between light and dark
    toggleThemeMode: function() {
        const currentMode = this.settings.theme_mode;
        const newMode = currentMode === 'light' ? 'dark' : 'light';
        
        this.updateTheme({ theme_mode: newMode });
        return newMode;
    },

    // Toggle RTL direction
    toggleRTL: function() {
        const isRTL = this.settings.rtl_enabled;
        this.updateTheme({ rtl_enabled: !isRTL });
        return !isRTL;
    },

    // Toggle sidebar collapsed state
    toggleSidebar: function() {
        const isCollapsed = this.settings.sidebar_collapsed;
        this.updateTheme({ sidebar_collapsed: !isCollapsed });
        return !isCollapsed;
    },

    // Reset theme to defaults
    resetTheme: function() {
        // Default settings
        const defaultSettings = {
            theme_mode: 'light',
            theme_color: 'blue',
            background_color: 'blue',
            sidebar_color: 'blue',
            font_family: 'Tajawal',
            font_size: 'medium',
            border_radius: 'medium',
            animation_speed: 'normal',
            layout_density: 'comfortable',
            sidebar_collapsed: false,
            rtl_enabled: true
        };
        
        // Update settings
        this.updateTheme(defaultSettings);
        return defaultSettings;
    }
};

// Alpine.js integration
document.addEventListener('alpine:init', () => {
    Alpine.data('themeManager', () => ({
        settings: ThemeManager.settings,
        
        init() {
            // Watch for changes to settings
            this.$watch('settings', (newSettings) => {
                ThemeManager.updateTheme(newSettings);
            }, { deep: true });
        },
        
        toggleThemeMode() {
            this.settings.theme_mode = ThemeManager.toggleThemeMode();
        },
        
        toggleRTL() {
            this.settings.rtl_enabled = ThemeManager.toggleRTL();
        },
        
        toggleSidebar() {
            this.settings.sidebar_collapsed = ThemeManager.toggleSidebar();
        },
        
        resetTheme() {
            this.settings = ThemeManager.resetTheme();
        }
    }));
});

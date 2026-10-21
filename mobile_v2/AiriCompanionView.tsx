/**
 * AiriCompanionView.tsx
 * Pure VRM 3D Companion Viewport - Clean, Spacious, Uncluttered Mobile Display.
 * Eliminates overlapping HUDs, double headers, and bottom-nav collisions.
 */
import React, { useState, useRef, useEffect } from 'react';
import {
    View,
    Text,
    StyleSheet,
    TouchableOpacity,
    ActivityIndicator,
    StatusBar,
    Animated,
    Platform,
} from 'react-native';

let NativeWebView: any = null;
try {
    const mod = require('react-native-webview');
    NativeWebView = mod.WebView || mod.default;
} catch (_e) {
    NativeWebView = null;
}

interface AiriCompanionViewProps {
    isConnected?: boolean;
    onVoiceTrigger?: () => void;
}

const VRM_VIEWER_URL = 'http://localhost:8080';

/**
 * Mobile Injected JS:
 * - Hides all desktop sidebars, desktop chat boxes, input fields, and toolbars
 * - Forces the Three.js canvas to fill 100% of the mobile viewport with correct touch handling
 */
const MOBILE_VIEWER_INJECT_JS = `
(function() {
    function cleanMobileViewport() {
        // Hide desktop UI elements
        var selectorsToHide = [
            '#sidebar-toggle',
            '#top-ui',
            '#chat-log',
            '#chat-input',
            '#chat-send',
            '#chat-mic',
            '.sidebar',
            '.chat-panel',
            '.desktop-controls',
            '.header-bar',
            '.status-bar',
            '.vrm-controls-panel',
            '#control-panel'
        ];

        selectorsToHide.forEach(function(sel) {
            var elements = document.querySelectorAll(sel);
            elements.forEach(function(el) {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
            });
        });

        // Stretch canvas to full mobile screen with zero margins
        var canvasContainer = document.getElementById('canvas-container') || document.getElementById('app') || document.body;
        if (canvasContainer) {
            canvasContainer.style.position = 'fixed';
            canvasContainer.style.top = '0';
            canvasContainer.style.left = '0';
            canvasContainer.style.width = '100vw';
            canvasContainer.style.height = '100vh';
            canvasContainer.style.margin = '0';
            canvasContainer.style.padding = '0';
            canvasContainer.style.overflow = 'hidden';
            canvasContainer.style.zIndex = '1';
        }

        var canvas = document.querySelector('canvas');
        if (canvas) {
            canvas.style.position = 'absolute';
            canvas.style.top = '0';
            canvas.style.left = '0';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.display = 'block';
            canvas.style.touchAction = 'none';
        }

        // Clean dark theme background
        document.body.style.backgroundColor = '#050609';
        document.body.style.margin = '0';
        document.body.style.padding = '0';
        document.body.style.overflow = 'hidden';
        document.documentElement.style.overflow = 'hidden';

        // Trigger Three.js resize event
        window.dispatchEvent(new Event('resize'));
    }

    cleanMobileViewport();
    setTimeout(cleanMobileViewport, 400);
    setTimeout(cleanMobileViewport, 1200);
    setTimeout(cleanMobileViewport, 2500);
    true;
})();
`;

export function AiriCompanionView({ isConnected = true, onVoiceTrigger }: AiriCompanionViewProps) {
    const webviewRef = useRef<any>(null);
    const [viewerLoaded, setViewerLoaded] = useState(false);
    const [viewerError, setViewerError] = useState(false);
    const [reloadKey, setReloadKey] = useState(0);
    const hintOpacity = useRef(new Animated.Value(1)).current;

    // Auto-fade gesture hint after 4 seconds
    useEffect(() => {
        const timer = setTimeout(() => {
            Animated.timing(hintOpacity, {
                toValue: 0,
                duration: 800,
                useNativeDriver: true,
            }).start();
        }, 4000);

        return () => clearTimeout(timer);
    }, [reloadKey]);

    const handleReload = () => {
        setViewerError(false);
        setViewerLoaded(false);
        setReloadKey(prev => prev + 1);
        hintOpacity.setValue(1);
    };

    return (
        <View style={styles.container}>
            <StatusBar barStyle="light-content" backgroundColor="#050609" />

            {/* ── Full-Bleed VRM Viewport (No Squeezing) ──────────────────── */}
            <View style={styles.viewport}>
                {!viewerError && NativeWebView ? (
                    <NativeWebView
                        key={reloadKey}
                        ref={webviewRef}
                        source={{ uri: VRM_VIEWER_URL }}
                        style={styles.webview}
                        javaScriptEnabled
                        allowsInlineMediaPlayback
                        mediaPlaybackRequiresUserAction={false}
                        allowsFullscreenVideo={false}
                        scrollEnabled={false}
                        bounces={false}
                        overScrollMode="never"
                        mixedContentMode="always"
                        originWhitelist={['*']}
                        injectedJavaScript={MOBILE_VIEWER_INJECT_JS}
                        onLoad={() => {
                            setViewerLoaded(true);
                            setTimeout(() => {
                                webviewRef.current?.injectJavaScript(MOBILE_VIEWER_INJECT_JS);
                            }, 300);
                        }}
                        onError={() => setViewerError(true)}
                        onHttpError={() => setViewerError(true)}
                        renderLoading={() => (
                            <View style={styles.loaderOverlay}>
                                <ActivityIndicator size="large" color="#00e5ff" />
                                <Text style={styles.loaderTitle}>Initializing Airi 3D VRM...</Text>
                                <Text style={styles.loaderSub}>Linking with port 8080</Text>
                            </View>
                        )}
                        startInLoadingState
                    />
                ) : (
                    /* Clean, Centered Offline View with Zero UI Cramping */
                    <View style={styles.errorOverlay}>
                        <View style={styles.errorAvatarCircle}>
                            <Text style={styles.errorIcon}>VRM</Text>
                        </View>
                        <Text style={styles.errorTitle}>Airi 3D VRM Standby</Text>
                        <Text style={styles.errorSub}>
                            Start the character viewer server on workstation:{'\n'}
                            <Text style={styles.codeText}>python helios-character/ai_server.py</Text>
                            {'\n\n'}Ensure ADB reverse bridge is active:{'\n'}
                            <Text style={styles.codeText}>adb reverse tcp:8080 tcp:8080</Text>
                        </Text>
                        <TouchableOpacity style={styles.retryBtn} onPress={handleReload}>
                            <Text style={styles.retryBtnText}>↺  CONNECT VRM VIEWPORT</Text>
                        </TouchableOpacity>
                    </View>
                )}

                {/* ── Discreet Single Top Floating Glass Control ────────────── */}
                <View style={styles.topGlassBar}>
                    <View style={styles.miniStatusPill}>
                        <View style={[styles.statusDot, !viewerError ? styles.dotOnline : styles.dotOffline]} />
                        <Text style={styles.miniStatusText}>
                            {!viewerError ? 'AIRI 3D' : 'STANDBY'}
                        </Text>
                    </View>

                    <View style={styles.topActionRow}>
                        {onVoiceTrigger && (
                            <TouchableOpacity style={styles.micQuickBtn} onPress={onVoiceTrigger}>
                                <Text style={styles.micQuickIcon}>MIC</Text>
                            </TouchableOpacity>
                        )}
                        <TouchableOpacity style={styles.refreshBtn} onPress={handleReload}>
                            <Text style={styles.refreshBtnText}>SYNC</Text>
                        </TouchableOpacity>
                    </View>
                </View>

                {/* ── Bottom Gesture Micro-Pill (Positioned Above Tab Bar) ──── */}
                <Animated.View style={[styles.bottomHintPill, { opacity: hintOpacity }]} pointerEvents="none">
                    <Text style={styles.bottomHintText}>DRAG TO ORBIT 3D AVATAR</Text>
                </Animated.View>
            </View>
        </View>
    );
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        backgroundColor: '#050609',
    },
    viewport: {
        flex: 1,
        position: 'relative',
        backgroundColor: '#050609',
    },
    webview: {
        flex: 1,
        backgroundColor: '#050609',
    },

    // Single Minimal Top Glass Bar
    topGlassBar: {
        position: 'absolute',
        top: Platform.OS === 'android' ? 12 : 8,
        left: 14,
        right: 14,
        flexDirection: 'row',
        justifyContent: 'space-between',
        alignItems: 'center',
        zIndex: 50,
        pointerEvents: 'box-none',
    },
    miniStatusPill: {
        flexDirection: 'row',
        alignItems: 'center',
        backgroundColor: 'rgba(9, 11, 17, 0.75)',
        borderWidth: 1,
        borderColor: 'rgba(0, 229, 255, 0.3)',
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: 16,
    },
    statusDot: {
        width: 6,
        height: 6,
        borderRadius: 3,
        marginRight: 6,
    },
    dotOnline: {
        backgroundColor: '#00e5ff',
        shadowColor: '#00e5ff',
        shadowOffset: { width: 0, height: 0 },
        shadowOpacity: 0.9,
        shadowRadius: 5,
    },
    dotOffline: {
        backgroundColor: '#ff4757',
    },
    miniStatusText: {
        color: '#ebf0f5',
        fontSize: 10,
        fontWeight: '800',
        letterSpacing: 1.2,
        fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
    },
    topActionRow: {
        flexDirection: 'row',
        alignItems: 'center',
        gap: 8,
    },
    micQuickBtn: {
        width: 32,
        height: 32,
        borderRadius: 16,
        backgroundColor: 'rgba(0, 229, 255, 0.15)',
        borderWidth: 1,
        borderColor: 'rgba(0, 229, 255, 0.4)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    micQuickIcon: {
        fontSize: 14,
    },
    refreshBtn: {
        width: 32,
        height: 32,
        borderRadius: 16,
        backgroundColor: 'rgba(15, 20, 30, 0.75)',
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.15)',
        justifyContent: 'center',
        alignItems: 'center',
    },
    refreshBtnText: {
        color: '#94a3b8',
        fontSize: 14,
        fontWeight: '700',
    },

    // Floating Hint (Safe above bottom nav bar: height 68 -> bottom: 84)
    bottomHintPill: {
        position: 'absolute',
        bottom: 84,
        alignSelf: 'center',
        backgroundColor: 'rgba(5, 7, 12, 0.7)',
        paddingHorizontal: 14,
        paddingVertical: 6,
        borderRadius: 18,
        borderWidth: 1,
        borderColor: 'rgba(255, 255, 255, 0.08)',
        zIndex: 40,
    },
    bottomHintText: {
        color: '#64748b',
        fontSize: 10,
        fontWeight: '600',
        letterSpacing: 0.8,
    },

    // Loader
    loaderOverlay: {
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: '#050609',
        justifyContent: 'center',
        alignItems: 'center',
        zIndex: 20,
    },
    loaderTitle: {
        color: '#f8fafc',
        fontSize: 14,
        fontWeight: '700',
        marginTop: 14,
        letterSpacing: 0.5,
    },
    loaderSub: {
        color: '#64748b',
        fontSize: 11,
        marginTop: 4,
    },

    // Standby Error Screen
    errorOverlay: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        paddingHorizontal: 28,
        backgroundColor: '#050609',
    },
    errorAvatarCircle: {
        width: 72,
        height: 72,
        borderRadius: 36,
        backgroundColor: 'rgba(0, 229, 255, 0.08)',
        borderWidth: 1.5,
        borderColor: 'rgba(0, 229, 255, 0.25)',
        justifyContent: 'center',
        alignItems: 'center',
        marginBottom: 16,
    },
    errorIcon: {
        fontSize: 32,
    },
    errorTitle: {
        color: '#f8fafc',
        fontSize: 18,
        fontWeight: '800',
        letterSpacing: 0.8,
        marginBottom: 10,
    },
    errorSub: {
        color: '#94a3b8',
        fontSize: 12,
        lineHeight: 18,
        textAlign: 'center',
        marginBottom: 24,
    },
    codeText: {
        color: '#00e5ff',
        fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
        fontWeight: '700',
    },
    retryBtn: {
        backgroundColor: 'rgba(0, 229, 255, 0.12)',
        borderWidth: 1,
        borderColor: '#00e5ff',
        paddingHorizontal: 20,
        paddingVertical: 12,
        borderRadius: 12,
    },
    retryBtnText: {
        color: '#00e5ff',
        fontSize: 12,
        fontWeight: '800',
        letterSpacing: 1.2,
    },
});

import React, { useState, useEffect, useRef } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  SafeAreaView,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  Alert,
  LogBox,
} from 'react-native';

LogBox.ignoreAllLogs(true);
import { StatusBar } from 'expo-status-bar';
import * as DocumentPicker from 'expo-document-picker';
import { HeliosClient, HeliosMessage, HikariMessage, DEFAULT_SERVER_URL } from './src/api/client';
import { AICoreWebView } from './AICoreWebView';
import { AiriCompanionView } from './AiriCompanionView';

// ── Types ────────────────────────────────────────────────────────────────────
interface TerminalLogItem {
  id: string;
  type: 'banner' | 'user' | 'step' | 'output' | 'diff' | 'system';
  content: string;
  state?: string;
  timestamp?: number;
}

interface ApprovalItem {
  requestId: string;
  tool: string;
  args: any;
  risk?: string;
}

type TabType = 'core' | 'terminal' | 'airi' | 'settings';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('core');
  const [terminalLogs, setTerminalLogs] = useState<TerminalLogItem[]>([
    {
      id: 'init-banner',
      type: 'banner',
      content: '✦ HIKARI CLI v2.0.76 // BUILD · THINK · EXECUTE\nAutonomous 8-Agent Coding Swarm connected to NVIDIA PAIR',
    },
  ]);
  const [terminalInput, setTerminalInput] = useState('');
  const [statusText, setStatusText] = useState('Connecting to HELIOS...');
  const [isConnected, setIsConnected] = useState(false);
  const [isHikariConnected, setIsHikariConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [uiState, setUiState] = useState<'idle' | 'listening' | 'thinking' | 'speaking' | 'amber'>('idle');

  // Pending Human-In-The-Loop Approval
  const [pendingApproval, setPendingApproval] = useState<ApprovalItem | null>(null);

  // Settings & Node Configuration
  const [serverUrlInput, setServerUrlInput] = useState(DEFAULT_SERVER_URL);
  const [pingLatency, setPingLatency] = useState<number | null>(null);
  const [pingStatus, setPingStatus] = useState<string>('');
  const [isPinging, setIsPinging] = useState(false);

  // GGUF Engine State
  const [localModelName, setLocalModelName] = useState<string | null>(null);
  const [ggufEngineType, setGgufEngineType] = useState<string>('Local GGUF Bridge');
  const [isTestingGguf, setIsTestingGguf] = useState(false);
  const [ggufTestResult, setGgufTestResult] = useState<string | null>(null);

  // Swarm & Model Meta
  const [activeModelMeta, setActiveModelMeta] = useState<{ model: string; category: string; agent: string } | null>({
    model: 'Swarm (Qwen 2.5-Coder / Devstral)',
    category: 'Coding Swarm',
    agent: 'Hikari Supervisor',
  });

  const clientRef = useRef<HeliosClient | null>(null);
  const terminalScrollRef = useRef<ScrollView>(null);

  // ── Voice Commands State ───────────────────────────────────────────────────
  const [voiceModalVisible, setVoiceModalVisible] = useState(false);
  const [voiceInputText, setVoiceInputText] = useState('');
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const [voiceFeedback, setVoiceFeedback] = useState<string | null>(null);

  // ── Client Initialization & Event Routing ──────────────────────────────────
  useEffect(() => {
    const client = new HeliosClient((msg: HeliosMessage) => {
      handleIncomingCoreMessage(msg);
    });

    clientRef.current = client;
    setServerUrlInput(client.serverUrl);
    setGgufEngineType(client.ggufEngineType);

    // Connect to Hikari Terminal stream
    client.connectHikari((hikariMsg: HikariMessage) => {
      handleIncomingHikariMessage(hikariMsg);
    });

    // Initial ping test
    setTimeout(() => {
      testPing(client.serverUrl);
    }, 1200);

    return () => {
      // Cleanup
    };
  }, []);

  const handleIncomingCoreMessage = (msg: HeliosMessage) => {
    if (msg.type === 'connection') {
      setIsConnected(Boolean(msg.connected));
      if (!msg.connected) {
        setUiState('idle');
      }
    } else if (msg.type === 'status') {
      setStatusText(msg.text || '');
    } else if (msg.type === 'ui_state') {
      if (msg.state && ['idle', 'listening', 'thinking', 'speaking', 'amber'].includes(msg.state)) {
        setUiState(msg.state as any);
      }
    } else if (msg.type === 'meta') {
      if (msg.model || msg.category) {
        setActiveModelMeta({
          model: msg.model || 'Auto-Routed',
          category: msg.category || 'General',
          agent: msg.agent || 'Supervisor',
        });
      }
    } else if (msg.type === 'approval_request') {
      setUiState('amber');
      setPendingApproval({
        requestId: msg.request_id || '',
        tool: msg.tool || 'Action',
        args: msg.args || {},
        risk: msg.risk || 'Moderate',
      });
    } else if (msg.type === 'chunk') {
      setUiState('speaking');
      // Append streaming chunk to terminal if on terminal
      setTerminalLogs(prev => {
        const last = prev[prev.length - 1];
        if (last && last.type === 'output') {
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...last,
            content: last.content + (msg.content || ''),
          };
          return updated;
        } else {
          return [
            ...prev,
            {
              id: String(Date.now()),
              type: 'output',
              content: msg.content || '',
            },
          ];
        }
      });
    } else if (msg.type === 'done') {
      setIsGenerating(false);
      setUiState('idle');
      setStatusText('Ready');
    }
  };

  const handleIncomingHikariMessage = (msg: HikariMessage) => {
    setIsHikariConnected(true);
    if (msg.type === 'banner') {
      setTerminalLogs(prev => [
        ...prev,
        {
          id: `banner-${Date.now()}`,
          type: 'banner',
          content: `✦ HIKARI CLI ${msg.version || 'v2.0'} // ${msg.workspace || 'isshin-2/helios'} [${msg.branch || 'main'}]\nModel: ${msg.model || 'Swarm'} | Provider: ${msg.provider || 'NVIDIA PAIR'}`,
        },
      ]);
    } else if (msg.type === 'step') {
      setUiState('thinking');
      setIsGenerating(true);
      setTerminalLogs(prev => [
        ...prev,
        {
          id: `step-${Date.now()}-${Math.random()}`,
          type: 'step',
          state: msg.state || 'STEP',
          content: msg.message || '',
        },
      ]);
    } else if (msg.type === 'output') {
      setTerminalLogs(prev => [
        ...prev,
        {
          id: `out-${Date.now()}-${Math.random()}`,
          type: msg.isDiff ? 'diff' : 'output',
          content: msg.text || '',
        },
      ]);
    } else if (msg.type === 'clear') {
      setTerminalLogs([]);
    } else if (msg.type === 'done') {
      setIsGenerating(false);
      setUiState('idle');
      setStatusText(msg.status || 'Ready');
    }
  };

  const sendTerminalCommand = (textToSend?: string) => {
    const query = (textToSend !== undefined ? textToSend : terminalInput).trim();
    if (!query) return;

    if (query === '/clear') {
      setTerminalLogs([]);
      if (textToSend === undefined) setTerminalInput('');
      return;
    }

    // Append user command
    setTerminalLogs(prev => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        type: 'user',
        content: query,
      },
    ]);

    setIsGenerating(true);
    setUiState('thinking');
    setStatusText('Hikari Swarm Executing...');

    if (clientRef.current) {
      clientRef.current.sendHikariCommand(query);
    }

    if (textToSend === undefined) setTerminalInput('');
  };

  const stopGeneration = () => {
    if (clientRef.current) {
      clientRef.current.stopGeneration();
      setIsGenerating(false);
      setUiState('idle');
      setStatusText('Halted by User');
    }
  };

  const handleApprovalResponse = (approved: boolean) => {
    if (!pendingApproval || !clientRef.current) return;
    clientRef.current.sendApproval(pendingApproval.requestId, approved, 'session');
    setTerminalLogs(prev => [
      ...prev,
      {
        id: String(Date.now()),
        type: 'system',
        content: `${approved ? '✓ Approved' : '✗ Denied'} tool execution: ${pendingApproval.tool}`,
      },
    ]);
    setPendingApproval(null);
    setUiState(approved ? 'thinking' : 'idle');
  };

  const executeVoiceCommand = (rawSpeech: string) => {
    const text = rawSpeech.trim();
    if (!text) return;

    setVoiceTranscript(text);
    const lower = text.toLowerCase();

    // 1. Navigation Commands
    if (lower.includes('airi') || lower.includes('companion') || lower.includes('3d') || lower.includes('vrm')) {
      setActiveTab('airi');
      setVoiceFeedback('Switched to Airi 3D Companion');
    } else if (lower.includes('terminal') || lower.includes('cli') || lower.includes('shell') || lower.includes('console')) {
      setActiveTab('terminal');
      setVoiceFeedback('Switched to Hikari Terminal');
    } else if (lower.includes('core') || lower.includes('ai core') || lower.includes('singularity')) {
      setActiveTab('core');
      setVoiceFeedback('Switched to AI Core');
    } else if (lower.includes('node') || lower.includes('setting') || lower.includes('config')) {
      setActiveTab('settings');
      setVoiceFeedback('Switched to Nodes & Engine Settings');
    }
    // 2. Control & Safety Commands
    else if (lower.includes('stop') || lower.includes('halt') || lower.includes('cancel') || lower.includes('abort')) {
      stopGeneration();
      setVoiceFeedback('Halted active generation');
    } else if (lower.includes('approve') || lower.includes('yes') || lower.includes('authorize')) {
      if (pendingApproval) {
        handleApprovalResponse(true);
        setVoiceFeedback(`Approved: ${pendingApproval.tool}`);
      } else {
        setVoiceFeedback('No pending approval request');
      }
    } else if (lower.includes('deny') || lower.includes('reject') || lower.includes('no')) {
      if (pendingApproval) {
        handleApprovalResponse(false);
        setVoiceFeedback(`Denied: ${pendingApproval.tool}`);
      } else {
        setVoiceFeedback('No pending approval request');
      }
    }
    // 3. Execution Commands
    else if (lower.startsWith('run ') || lower.startsWith('execute ')) {
      const cmd = text.replace(/^(run|execute)\s+/i, '');
      setActiveTab('terminal');
      if (clientRef.current) {
        clientRef.current.sendHikariCommand(cmd);
      }
      setVoiceFeedback(`Executed in Hikari: ${cmd}`);
    } else if (lower === 'status' || lower.includes('system status')) {
      if (clientRef.current) {
        clientRef.current.sendMessage('/status');
      }
      setActiveTab('core');
      setVoiceFeedback('Queried system status');
    } else if (lower === 'models' || lower.includes('list models')) {
      if (clientRef.current) {
        clientRef.current.sendMessage('/models');
      }
      setActiveTab('core');
      setVoiceFeedback('Queried active models');
    } else if (lower === 'diff' || lower.includes('show diff')) {
      if (clientRef.current) {
        clientRef.current.sendMessage('/diff');
      }
      setActiveTab('terminal');
      setVoiceFeedback('Queried git diff');
    }
    // 4. General Prompts to AI Core
    else {
      if (clientRef.current) {
        setIsGenerating(true);
        setUiState('thinking');
        clientRef.current.sendMessage(text);
      }
      setActiveTab('core');
      setVoiceFeedback(`Dispatched prompt: "${text}"`);
    }

    setTimeout(() => {
      setVoiceModalVisible(false);
      setVoiceFeedback(null);
    }, 1400);
  };

  const testPing = async (urlToCheck?: string) => {
    if (!clientRef.current) return;
    setIsPinging(true);
    const result = await clientRef.current.pingServer(urlToCheck);
    setPingLatency(result.latencyMs);
    setPingStatus(result.statusText || '');
    setIsPinging(false);
  };

  const saveServerEndpoint = async () => {
    if (!clientRef.current) return;
    await clientRef.current.setServerUrl(serverUrlInput);
    testPing(serverUrlInput);
    Alert.alert('Endpoint Saved', `HELIOS mobile will connect to: ${serverUrlInput}`);
  };

  const pickLocalGGUF = async () => {
    try {
      const res = await DocumentPicker.getDocumentAsync({
        type: '*/*',
        copyToCacheDirectory: true,
      });
      if (!res.canceled && res.assets && res.assets.length > 0 && clientRef.current) {
        const asset = res.assets[0];
        let path = asset.uri;
        if (path.startsWith('file://')) path = path.replace('file://', '');
        setStatusText('Mounting GGUF weights...');
        const ok = await clientRef.current.setupOfflineModel(path, asset.name);
        if (ok) {
          setLocalModelName(asset.name);
          setGgufEngineType(clientRef.current.ggufEngineType);
          Alert.alert('GGUF Model Mounted', `Loaded ${asset.name} via ${clientRef.current.ggufEngineType}.`);
        } else {
          Alert.alert('Load Failed', 'Could not mount GGUF weights.');
        }
      }
    } catch (err: any) {
      console.error(err);
      Alert.alert('Error', err.message || 'File selection failed.');
    }
  };

  const runGgufTest = async () => {
    if (!clientRef.current) return;
    setIsTestingGguf(true);
    setGgufTestResult(null);
    const res = await clientRef.current.testGgufEngine('Hello HELIOS, verify GGUF inference');
    setIsTestingGguf(false);
    setGgufTestResult(`${res.ok ? '✓ PASS' : '✗ FAIL'} (${res.latencyMs} ms)\n${res.response}`);
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="light" />

      {/* Top Telemetry Header - only display on non-Airi tabs to prevent double headers and cramped viewport */}
      {activeTab !== 'airi' && (
        <View style={styles.topBar}>
          <View style={styles.brandRow}>
            <View style={styles.logoBadge}>
              <Text style={styles.logoBadgeText}>HELIOS</Text>
            </View>
            <View style={styles.statusPill}>
              <View style={[styles.statusDot, isConnected ? styles.dotOnline : styles.dotOffline]} />
              <Text style={styles.statusPillText}>
                {isConnected ? `ONLINE (${pingLatency !== null ? `${pingLatency}ms` : 'LINK'})` : 'OFFLINE'}
              </Text>
            </View>
          </View>

          <Text style={styles.subStatusText} numberOfLines={1}>
            {statusText}
          </Text>
        </View>
      )}

      {/* Main Body per Tab */}
      <View style={styles.contentContainer}>
        {/* ── Tab 1: AI CORE (Morphic Reactive States & Voice Link) ──────────── */}
        {activeTab === 'core' && (
          <View style={styles.coreTabContainer}>
            <AICoreWebView
              state={uiState}
              question={pendingApproval ? `AUTHORIZE: ${pendingApproval.tool}` : undefined}
              options={
                pendingApproval
                  ? ['APPROVE // Execute', 'DENY // Reject']
                  : ['/status', '/models', '/diff', 'Analyze active repository']
              }
              onVoiceTrigger={() => setVoiceModalVisible(true)}
              onAction={(act) => {
                if (pendingApproval) {
                  const isApprove = act.toLowerCase().includes('approve') || act.toLowerCase().includes('yes');
                  handleApprovalResponse(isApprove);
                } else {
                  // Direct prompt to HELIOS Core
                  if (clientRef.current) {
                    setIsGenerating(true);
                    setUiState('thinking');
                    clientRef.current.sendMessage(act);
                  }
                }
              }}
            />
          </View>
        )}

        {/* ── Tab 2: HIKARI TERMINAL ────────────────────────────────────────── */}
        {activeTab === 'terminal' && (
          <KeyboardAvoidingView
            style={styles.terminalContainer}
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          >
            {/* Terminal Workspace Status Sub-bar */}
            <View style={styles.terminalSubBar}>
              <Text style={styles.terminalSubText}>
                WORKSPACE: <Text style={styles.cyanText}>isshin-2/helios</Text> · git:(<Text style={styles.cyanText}>main</Text>) · SWARM: HIKARI
              </Text>
              <View style={[styles.terminalDot, isHikariConnected ? styles.dotOnline : styles.dotOffline]} />
            </View>

            {/* Quick Command Chips */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chipScroll}>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/help')}>
                <Text style={styles.chipText}>/help</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/models')}>
                <Text style={styles.chipText}>/models</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/diff')}>
                <Text style={styles.chipText}>/diff</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/review')}>
                <Text style={styles.chipText}>/review</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/test')}>
                <Text style={styles.chipText}>/test</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.chip} onPress={() => sendTerminalCommand('/clear')}>
                <Text style={styles.chipText}>/clear</Text>
              </TouchableOpacity>
            </ScrollView>

            {/* Terminal Live Output Log */}
            <ScrollView
              style={styles.terminalLogList}
              ref={terminalScrollRef}
              onContentSizeChange={() => terminalScrollRef.current?.scrollToEnd({ animated: true })}
            >
              {terminalLogs.map((item) => (
                <View key={item.id} style={styles.logRow}>
                  {item.type === 'banner' && (
                    <View style={styles.bannerBox}>
                      <Text style={styles.bannerText}>{item.content}</Text>
                    </View>
                  )}
                  {item.type === 'user' && (
                    <View style={styles.userPromptRow}>
                      <Text style={styles.promptSign}>hikari ❯ </Text>
                      <Text style={styles.promptText}>{item.content}</Text>
                    </View>
                  )}
                  {item.type === 'step' && (
                    <View style={styles.stepBadgeRow}>
                      <View style={[styles.stepBadge, getStepBadgeStyle(item.state)]}>
                        <Text style={styles.stepBadgeText}>[{item.state || 'STEP'}]</Text>
                      </View>
                      <Text style={styles.stepMessageText}>{item.content}</Text>
                    </View>
                  )}
                  {item.type === 'output' && (
                    <Text style={styles.outputText}>{item.content}</Text>
                  )}
                  {item.type === 'diff' && (
                    <View style={styles.diffBox}>
                      <Text style={styles.diffText}>{item.content}</Text>
                    </View>
                  )}
                  {item.type === 'system' && (
                    <Text style={styles.systemText}>{item.content}</Text>
                  )}
                </View>
              ))}

              {isGenerating && (
                <View style={styles.executingRow}>
                  <ActivityIndicator size="small" color="#00e5ff" />
                  <Text style={styles.executingText}>Hikari Swarm synthesizing & executing tools...</Text>
                </View>
              )}
            </ScrollView>

            {/* Stop Generation Button if Active */}
            {isGenerating && (
              <TouchableOpacity style={styles.stopBtn} onPress={stopGeneration}>
                <Text style={styles.stopBtnText}>[HALT] Interrupt / Stop Execution</Text>
              </TouchableOpacity>
            )}

            {/* Terminal Input Row */}
            <View style={styles.terminalInputBar}>
              <Text style={styles.promptSign}>hikari &gt;</Text>
              <TextInput
                style={styles.terminalInputField}
                value={terminalInput}
                onChangeText={setTerminalInput}
                placeholder="Enter command or objective..."
                placeholderTextColor="#475569"
                onSubmitEditing={() => sendTerminalCommand()}
                autoCapitalize="none"
              />
              <TouchableOpacity
                style={[styles.terminalSendBtn, !terminalInput.trim() && styles.terminalSendBtnDisabled]}
                onPress={() => sendTerminalCommand()}
                disabled={!terminalInput.trim()}
              >
                <Text style={styles.terminalSendBtnText}>RUN</Text>
              </TouchableOpacity>
            </View>
          </KeyboardAvoidingView>
        )}

        {/* ── Tab 3: AIRI 3D VRM COMPANION (Pure Spacious VRM Viewport) ────── */}
        {activeTab === 'airi' && (
          <View style={styles.airiTabContainer}>
            <AiriCompanionView
              isConnected={isConnected}
              onVoiceTrigger={() => setVoiceModalVisible(true)}
            />
          </View>
        )}

        {/* ── Tab 4: NODES & GGUF ENGINE SETTINGS ───────────────────────────── */}
        {activeTab === 'settings' && (
          <ScrollView style={styles.settingsContainer}>
            {/* Server Endpoint Card */}
            <Text style={styles.sectionTitle}>[LINK] Server Endpoint &amp; Workstation Link</Text>
            <View style={styles.card}>
              <Text style={styles.inputLabel}>HELIOS Core Server URL:</Text>
              <TextInput
                style={styles.settingInput}
                value={serverUrlInput}
                onChangeText={setServerUrlInput}
                placeholder="http://127.0.0.1:8000"
                placeholderTextColor="#64748b"
                autoCapitalize="none"
              />
              <View style={styles.btnRow}>
                <TouchableOpacity style={styles.primaryBtn} onPress={saveServerEndpoint}>
                  <Text style={styles.primaryBtnText}>Save &amp; Reconnect</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.secondaryBtn} onPress={() => testPing(serverUrlInput)}>
                  {isPinging ? (
                    <ActivityIndicator size="small" color="#00e5ff" />
                  ) : (
                    <Text style={styles.secondaryBtnText}>Test Ping</Text>
                  )}
                </TouchableOpacity>
              </View>
              {pingStatus ? (
                <Text style={styles.pingResultText}>
                  Status: {pingStatus} {pingLatency !== null ? `(${pingLatency} ms)` : ''}
                </Text>
              ) : null}
            </View>

            {/* Offline On-Device GGUF Engine Card */}
            <Text style={styles.sectionTitle}>[ENGINE] Offline GGUF Engine</Text>
            <View style={styles.card}>
              <View style={styles.ggufHeaderRow}>
                <Text style={styles.cardTitle}>GGUF Inference Engine</Text>
                <View style={styles.ggufBadge}>
                  <Text style={styles.ggufBadgeText}>{ggufEngineType}</Text>
                </View>
              </View>
              <Text style={styles.cardBody}>
                Executes quantized .gguf model weights on-device with zero network latency. Works in both Expo Go development mode and standalone builds.
              </Text>
              <Text style={styles.modelStatusText}>
                Active Model: {localModelName || 'Default GGUF Offline Model'}
              </Text>

              <View style={styles.btnRow}>
                <TouchableOpacity style={styles.loadModelBtn} onPress={pickLocalGGUF}>
                  <Text style={styles.loadModelBtnText}>SELECT GGUF FILE</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.testGgufBtn} onPress={runGgufTest}>
                  {isTestingGguf ? (
                    <ActivityIndicator size="small" color="#00e5ff" />
                  ) : (
                    <Text style={styles.testGgufBtnText}>TEST INFERENCE</Text>
                  )}
                </TouchableOpacity>
              </View>

              {ggufTestResult && (
                <View style={styles.ggufResultBox}>
                  <Text style={styles.ggufResultText}>{ggufTestResult}</Text>
                </View>
              )}
            </View>

            {/* Dedicated Workstation Telemetry */}
            <Text style={styles.sectionTitle}>[CLUSTER] NVIDIA PAIR Telemetry</Text>
            <View style={styles.card}>
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle}>NVIDIA GPU Cluster Node</Text>
                <View style={[styles.miniDot, isConnected ? styles.dotOnline : styles.dotOffline]} />
              </View>
              <Text style={styles.cardBody}>
                Dedicated GPU VRAM · Host RAM Pool · Headless Wake-on-LAN · Inter-node PAIR Cluster
              </Text>
              <View style={styles.statGrid}>
                <View style={styles.statBox}>
                  <Text style={styles.statLabel}>SWARM</Text>
                  <Text style={styles.statValue}>8 Agents</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statLabel}>PORT 8000</Text>
                  <Text style={styles.statValue}>HELIOS Core</Text>
                </View>
                <View style={styles.statBox}>
                  <Text style={styles.statLabel}>PORT 8080</Text>
                  <Text style={styles.statValue}>Airi VRM</Text>
                </View>
              </View>
            </View>
          </ScrollView>
        )}
      </View>

      {/* Human-In-The-Loop Approval Modal */}
      {pendingApproval && (
        <Modal transparent animationType="fade" visible={Boolean(pendingApproval)}>
          <View style={styles.modalBackdrop}>
            <View style={styles.modalCard}>
              <View style={styles.modalHeader}>
                <Text style={styles.modalIcon}>[!]</Text>
                <Text style={styles.modalTitle}>Permission Required</Text>
              </View>
              <Text style={styles.modalBody}>
                HELIOS Sandbox requires authorization to execute tool:
              </Text>
              <View style={styles.codeBlock}>
                <Text style={styles.codeText}>Action: {pendingApproval.tool}</Text>
                <Text style={styles.codeSubText}>{JSON.stringify(pendingApproval.args, null, 2)}</Text>
              </View>
              <View style={styles.modalBtnRow}>
                <TouchableOpacity style={styles.denyBtn} onPress={() => handleApprovalResponse(false)}>
                  <Text style={styles.denyBtnText}>Deny</Text>
                </TouchableOpacity>
                <TouchableOpacity style={styles.approveBtn} onPress={() => handleApprovalResponse(true)}>
                  <Text style={styles.approveBtnText}>Approve</Text>
                </TouchableOpacity>
              </View>
            </View>
          </View>
        </Modal>
      )}

      {/* ── Floating Cyber Voice Command FAB (Instant Voice Link) ─────────── */}
      <TouchableOpacity
        style={styles.voiceFab}
        activeOpacity={0.85}
        onPress={() => {
          setVoiceTranscript('');
          setVoiceFeedback(null);
          setVoiceModalVisible(true);
        }}
      >
        <Text style={styles.voiceFabIcon}>VOX</Text>
      </TouchableOpacity>

      {/* ── Cyber Voice Commands Modal ────────────────────────────────────── */}
      <Modal
        transparent
        animationType="fade"
        visible={voiceModalVisible}
        onRequestClose={() => setVoiceModalVisible(false)}
      >
        <TouchableOpacity
          style={styles.voiceModalBackdrop}
          activeOpacity={1}
          onPress={() => setVoiceModalVisible(false)}
        >
          <TouchableOpacity activeOpacity={1} style={styles.voiceModalCard}>
            <View style={styles.voiceModalHeader}>
              <View style={styles.voiceHeaderTitleRow}>
                <View style={styles.voicePulsingDot} />
                <Text style={styles.voiceModalTitle}>NEURAL VOICE COMMAND</Text>
              </View>
              <TouchableOpacity
                onPress={() => setVoiceModalVisible(false)}
                style={styles.voiceCloseBtn}
                hitSlop={{ top: 12, bottom: 12, left: 12, right: 12 }}
              >
                <Text style={styles.voiceCloseText}>X</Text>
              </TouchableOpacity>
            </View>

            {/* Sonic Wave Equalizer Simulation */}
            <View style={styles.voiceWaveContainer}>
              <View style={[styles.voiceWaveBar, { height: 16 }]} />
              <View style={[styles.voiceWaveBar, { height: 32 }]} />
              <View style={[styles.voiceWaveBar, { height: 50, backgroundColor: '#00e5ff' }]} />
              <View style={[styles.voiceWaveBar, { height: 28 }]} />
              <View style={[styles.voiceWaveBar, { height: 44, backgroundColor: '#00e5ff' }]} />
              <View style={[styles.voiceWaveBar, { height: 20 }]} />
            </View>

            <Text style={styles.voiceListeningStatus}>
              {voiceFeedback
                ? `[OK] ${voiceFeedback}`
                : voiceTranscript
                ? `"${voiceTranscript}"`
                : 'Listening for command or query...'}
            </Text>

            {/* Quick Voice Command Chips */}
            <Text style={styles.voiceChipLabel}>POPULAR VOICE COMMANDS:</Text>
            <View style={styles.voiceChipGrid}>
              {[
                { label: '/status', cmd: 'status' },
                { label: 'Airi 3D', cmd: 'switch to airi' },
                { label: 'Terminal', cmd: 'switch to terminal' },
                { label: 'Models', cmd: 'models' },
                { label: 'Git Diff', cmd: 'diff' },
                { label: 'Halt', cmd: 'halt' },
                { label: 'Approve', cmd: 'approve' },
                { label: 'Deny', cmd: 'deny' },
              ].map((c, i) => (
                <TouchableOpacity
                  key={i}
                  style={styles.voiceChip}
                  onPress={() => executeVoiceCommand(c.cmd)}
                >
                  <Text style={styles.voiceChipText}>{c.label}</Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Direct Voice Input Row */}
            <View style={styles.voiceInputRow}>
              <TextInput
                style={styles.voiceTextInput}
                placeholder="Speak or type command..."
                placeholderTextColor="#64748b"
                value={voiceInputText}
                onChangeText={setVoiceInputText}
                onSubmitEditing={() => {
                  if (voiceInputText.trim()) {
                    executeVoiceCommand(voiceInputText);
                    setVoiceInputText('');
                  }
                }}
                autoCapitalize="none"
                autoFocus
              />
              <TouchableOpacity
                style={styles.voiceSendBtn}
                onPress={() => {
                  if (voiceInputText.trim()) {
                    executeVoiceCommand(voiceInputText);
                    setVoiceInputText('');
                  }
                }}
              >
                <Text style={styles.voiceSendBtnText}>VOICE</Text>
              </TouchableOpacity>
            </View>
          </TouchableOpacity>
        </TouchableOpacity>
      </Modal>

      {/* ── Bottom Floating Cyberpunk Navigation Bar (Swarm Removed) ─────── */}
      <View style={styles.bottomNav}>
        <TouchableOpacity
          style={[styles.navItem, activeTab === 'core' && styles.navItemActive]}
          onPress={() => setActiveTab('core')}
        >
          <Text style={[styles.navIcon, activeTab === 'core' && styles.navTextActive]}>CORE</Text>
          <Text style={[styles.navText, activeTab === 'core' && styles.navTextActive]}>AI Core</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === 'terminal' && styles.navItemActive]}
          onPress={() => setActiveTab('terminal')}
        >
          <Text style={[styles.navIcon, activeTab === 'terminal' && styles.navTextActive]}>CLI</Text>
          <Text style={[styles.navText, activeTab === 'terminal' && styles.navTextActive]}>Terminal</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === 'airi' && styles.navItemActive]}
          onPress={() => setActiveTab('airi')}
        >
          <Text style={[styles.navIcon, activeTab === 'airi' && styles.navTextActive]}>VRM</Text>
          <Text style={[styles.navText, activeTab === 'airi' && styles.navTextActive]}>Airi</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.navItem, activeTab === 'settings' && styles.navItemActive]}
          onPress={() => setActiveTab('settings')}
        >
          <Text style={[styles.navIcon, activeTab === 'settings' && styles.navTextActive]}>NODE</Text>
          <Text style={[styles.navText, activeTab === 'settings' && styles.navTextActive]}>Nodes</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

function getStepBadgeStyle(state?: string) {
  switch (state) {
    case 'ANALYZE':
      return { borderColor: '#00e5ff', backgroundColor: 'rgba(0, 229, 255, 0.15)' };
    case 'PLAN':
      return { borderColor: '#e056fd', backgroundColor: 'rgba(224, 86, 253, 0.15)' };
    case 'ARCHITECT':
      return { borderColor: '#686de0', backgroundColor: 'rgba(104, 109, 224, 0.15)' };
    case 'EXECUTE':
      return { borderColor: '#2ed573', backgroundColor: 'rgba(46, 213, 115, 0.15)' };
    case 'VERIFY':
      return { borderColor: '#ffa502', backgroundColor: 'rgba(255, 165, 2, 0.15)' };
    case 'REPAIR':
      return { borderColor: '#ff4757', backgroundColor: 'rgba(255, 71, 87, 0.15)' };
    case 'REVIEW':
      return { borderColor: '#70a1ff', backgroundColor: 'rgba(112, 161, 255, 0.15)' };
    case 'SECURITY_REVIEW':
      return { borderColor: '#ff3838', backgroundColor: 'rgba(255, 56, 56, 0.2)' };
    default:
      return { borderColor: '#00e5ff', backgroundColor: 'rgba(0, 229, 255, 0.1)' };
  }
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: '#07080c',
  },
  topBar: {
    paddingHorizontal: 16,
    paddingTop: Platform.OS === 'android' ? 36 : 10,
    paddingBottom: 8,
    backgroundColor: '#050609',
    borderBottomWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.15)',
  },
  brandRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  logoBadge: {
    backgroundColor: 'rgba(0, 229, 255, 0.1)',
    borderColor: '#00e5ff',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  logoBadgeText: {
    color: '#00e5ff',
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  statusPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#10131d',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  dotOnline: {
    backgroundColor: '#00ff88',
  },
  dotOffline: {
    backgroundColor: '#ff3366',
  },
  statusPillText: {
    color: '#d0d7de',
    fontSize: 11,
    fontWeight: '700',
  },
  subStatusText: {
    color: '#8b949e',
    fontSize: 11,
    marginTop: 4,
    fontStyle: 'italic',
  },
  contentContainer: {
    flex: 1,
  },

  // Core Tab
  coreTabContainer: {
    flex: 1,
    backgroundColor: '#07080c',
  },

  // Terminal Tab
  terminalContainer: {
    flex: 1,
    backgroundColor: '#07080c',
  },
  terminalSubBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: '#0a0d14',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  terminalSubText: {
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '600',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  cyanText: {
    color: '#00e5ff',
    fontWeight: '700',
  },
  terminalDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  chipScroll: {
    maxHeight: 44,
    paddingHorizontal: 12,
    paddingVertical: 6,
    backgroundColor: '#07080c',
  },
  chip: {
    backgroundColor: '#0f131d',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.25)',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    marginRight: 8,
  },
  chipText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '700',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  terminalLogList: {
    flex: 1,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  logRow: {
    marginBottom: 8,
  },
  bannerBox: {
    backgroundColor: 'rgba(0, 229, 255, 0.05)',
    borderLeftWidth: 3,
    borderColor: '#00e5ff',
    padding: 8,
    borderRadius: 4,
  },
  bannerText: {
    color: '#00e5ff',
    fontSize: 11,
    lineHeight: 16,
    fontWeight: '700',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  userPromptRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: 'rgba(255, 255, 255, 0.03)',
    padding: 6,
    borderRadius: 4,
  },
  promptSign: {
    color: '#00e5ff',
    fontWeight: '800',
    fontSize: 12,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  promptText: {
    flex: 1,
    color: '#ffffff',
    fontWeight: '700',
    fontSize: 12,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  stepBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginVertical: 2,
  },
  stepBadge: {
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  stepBadgeText: {
    color: '#ffffff',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 1,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  stepMessageText: {
    flex: 1,
    color: '#cbd5e1',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  outputText: {
    color: '#e2e8f0',
    fontSize: 12,
    lineHeight: 17,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  diffBox: {
    backgroundColor: '#0a0d14',
    borderWidth: 1,
    borderColor: 'rgba(46, 213, 115, 0.3)',
    borderRadius: 6,
    padding: 10,
    marginVertical: 4,
  },
  diffText: {
    color: '#2ed573',
    fontSize: 11,
    lineHeight: 16,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  systemText: {
    color: '#94a3b8',
    fontSize: 11,
    fontStyle: 'italic',
  },
  executingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 6,
  },
  executingText: {
    color: '#00e5ff',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  stopBtn: {
    backgroundColor: 'rgba(255, 71, 87, 0.15)',
    borderWidth: 1,
    borderColor: '#ff4757',
    paddingVertical: 8,
    alignItems: 'center',
    marginHorizontal: 14,
    marginBottom: 6,
    borderRadius: 8,
  },
  stopBtnText: {
    color: '#ff4757',
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 1,
  },
  terminalInputBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#0a0d14',
    borderTopWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.2)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    gap: 8,
  },
  terminalInputField: {
    flex: 1,
    color: '#ffffff',
    fontSize: 12,
    paddingVertical: 6,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  terminalSendBtn: {
    backgroundColor: 'rgba(0, 229, 255, 0.15)',
    borderWidth: 1,
    borderColor: '#00e5ff',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  terminalSendBtnDisabled: {
    opacity: 0.3,
  },
  terminalSendBtnText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '800',
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },

  // Settings / Nodes Tab
  settingsContainer: {
    flex: 1,
    padding: 16,
    backgroundColor: '#07080c',
  },
  sectionTitle: {
    color: '#00e5ff',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.2,
    marginTop: 10,
    marginBottom: 8,
    textTransform: 'uppercase',
  },
  card: {
    backgroundColor: '#0c0f17',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    padding: 14,
    marginBottom: 14,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  cardTitle: {
    color: '#f8fafc',
    fontSize: 13,
    fontWeight: '700',
  },
  cardBody: {
    color: '#94a3b8',
    fontSize: 12,
    lineHeight: 18,
    marginBottom: 10,
  },
  miniDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  inputLabel: {
    color: '#94a3b8',
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 6,
  },
  settingInput: {
    backgroundColor: '#050609',
    borderWidth: 1,
    borderColor: '#1e293b',
    borderRadius: 8,
    color: '#ffffff',
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 12,
    marginBottom: 10,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  btnRow: {
    flexDirection: 'row',
    gap: 8,
  },
  primaryBtn: {
    flex: 1,
    backgroundColor: 'rgba(0, 229, 255, 0.15)',
    borderWidth: 1,
    borderColor: '#00e5ff',
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  primaryBtnText: {
    color: '#00e5ff',
    fontSize: 12,
    fontWeight: '800',
  },
  secondaryBtn: {
    backgroundColor: '#10141e',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryBtnText: {
    color: '#e2e8f0',
    fontSize: 12,
    fontWeight: '700',
  },
  pingResultText: {
    color: '#00e5ff',
    fontSize: 11,
    marginTop: 8,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  ggufHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  ggufBadge: {
    backgroundColor: 'rgba(0, 229, 255, 0.12)',
    borderWidth: 1,
    borderColor: '#00e5ff',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 6,
  },
  ggufBadgeText: {
    color: '#00e5ff',
    fontSize: 10,
    fontWeight: '800',
  },
  modelStatusText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 10,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  loadModelBtn: {
    flex: 1,
    backgroundColor: '#10141e',
    borderWidth: 1,
    borderColor: '#00e5ff',
    borderRadius: 8,
    paddingVertical: 9,
    alignItems: 'center',
  },
  loadModelBtnText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '800',
  },
  testGgufBtn: {
    backgroundColor: 'rgba(0, 229, 255, 0.15)',
    borderWidth: 1,
    borderColor: '#00e5ff',
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  testGgufBtnText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '800',
  },
  ggufResultBox: {
    backgroundColor: '#050609',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
    borderRadius: 6,
    padding: 8,
    marginTop: 10,
  },
  ggufResultText: {
    color: '#cbd5e1',
    fontSize: 11,
    lineHeight: 16,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  statGrid: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 6,
  },
  statBox: {
    flex: 1,
    backgroundColor: '#050609',
    borderRadius: 6,
    padding: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.05)',
  },
  statLabel: {
    color: '#64748b',
    fontSize: 9,
    fontWeight: '700',
  },
  statValue: {
    color: '#f8fafc',
    fontSize: 11,
    fontWeight: '800',
    marginTop: 2,
  },

  // Modal
  modalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.85)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    backgroundColor: '#0e111a',
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: '#ff9f43',
    padding: 18,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 10,
  },
  modalIcon: {
    fontSize: 20,
  },
  modalTitle: {
    color: '#ff9f43',
    fontSize: 15,
    fontWeight: '800',
  },
  modalBody: {
    color: '#cbd5e1',
    fontSize: 12,
    marginBottom: 8,
  },
  codeBlock: {
    backgroundColor: '#050609',
    borderRadius: 6,
    padding: 10,
    borderWidth: 1,
    borderColor: '#1e293b',
    marginBottom: 14,
  },
  codeText: {
    color: '#00e5ff',
    fontWeight: '700',
    fontSize: 11,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  codeSubText: {
    color: '#94a3b8',
    fontSize: 10,
    marginTop: 4,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  modalBtnRow: {
    flexDirection: 'row',
    gap: 10,
  },
  denyBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: '#ff4757',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  denyBtnText: {
    color: '#ff4757',
    fontWeight: '800',
    fontSize: 12,
  },
  approveBtn: {
    flex: 1,
    backgroundColor: 'rgba(0, 229, 255, 0.2)',
    borderWidth: 1,
    borderColor: '#00e5ff',
    paddingVertical: 10,
    borderRadius: 8,
    alignItems: 'center',
  },
  approveBtnText: {
    color: '#00e5ff',
    fontWeight: '800',
    fontSize: 12,
  },

  // Bottom Floating Navigation
  bottomNav: {
    flexDirection: 'row',
    backgroundColor: '#050609',
    borderTopWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.15)',
    paddingVertical: 8,
    paddingHorizontal: 8,
    justifyContent: 'space-around',
  },
  navItem: {
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 14,
    borderRadius: 8,
  },
  navItemActive: {
    backgroundColor: 'rgba(0, 229, 255, 0.08)',
  },
  navIcon: {
    fontSize: 18,
    opacity: 0.6,
  },
  navText: {
    color: '#64748b',
    fontSize: 10,
    fontWeight: '700',
    marginTop: 2,
    letterSpacing: 0.5,
  },
  navTextActive: {
    color: '#00e5ff',
    opacity: 1,
  },

  // Airi Full-Bleed Tab Container (No Cramping)
  airiTabContainer: {
    flex: 1,
    backgroundColor: '#050609',
  },

  // Floating Cyber Voice Command FAB
  voiceFab: {
    position: 'absolute',
    bottom: 80,
    right: 18,
    width: 52,
    height: 52,
    borderRadius: 26,
    backgroundColor: '#090d16',
    borderWidth: 1.5,
    borderColor: '#00e5ff',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 14,
    elevation: 10,
    zIndex: 90,
  },
  voiceFabIcon: {
    fontSize: 22,
  },

  // Cyber Voice Commands Modal
  voiceModalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(3, 5, 8, 0.88)',
    justifyContent: 'flex-end',
    padding: 16,
    paddingBottom: Platform.OS === 'android' ? 24 : 34,
  },
  voiceModalCard: {
    backgroundColor: '#0c0f18',
    borderWidth: 1.5,
    borderColor: '#00e5ff',
    borderRadius: 20,
    padding: 20,
    shadowColor: '#00e5ff',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 16,
  },
  voiceModalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  voiceHeaderTitleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  voicePulsingDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#00e5ff',
  },
  voiceModalTitle: {
    color: '#00e5ff',
    fontSize: 12,
    fontWeight: '900',
    letterSpacing: 1.5,
    fontFamily: Platform.OS === 'ios' ? 'Courier' : 'monospace',
  },
  voiceCloseBtn: {
    padding: 4,
  },
  voiceCloseText: {
    color: '#94a3b8',
    fontSize: 14,
    fontWeight: '800',
  },
  voiceWaveContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    height: 60,
    marginVertical: 10,
  },
  voiceWaveBar: {
    width: 6,
    borderRadius: 3,
    backgroundColor: 'rgba(0, 229, 255, 0.4)',
  },
  voiceListeningStatus: {
    color: '#f8fafc',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 16,
    fontStyle: 'italic',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  voiceChipLabel: {
    color: '#64748b',
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
    marginBottom: 8,
  },
  voiceChipGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  voiceChip: {
    backgroundColor: 'rgba(0, 229, 255, 0.08)',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.25)',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
  },
  voiceChipText: {
    color: '#00e5ff',
    fontSize: 11,
    fontWeight: '700',
  },
  voiceInputRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#05070c',
    borderWidth: 1,
    borderColor: 'rgba(0, 229, 255, 0.3)',
    borderRadius: 12,
    paddingHorizontal: 10,
    paddingVertical: 4,
    gap: 8,
  },
  voiceTextInput: {
    flex: 1,
    color: '#f8fafc',
    fontSize: 13,
    paddingVertical: 8,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  voiceSendBtn: {
    backgroundColor: '#00e5ff',
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  voiceSendBtnText: {
    color: '#050609',
    fontSize: 11,
    fontWeight: '900',
    letterSpacing: 1,
  },
});

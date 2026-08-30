import React, { useState, useEffect, useRef } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, FlatList, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { router } from 'expo-router';
import { helios, ChatMessage } from '../services/HeliosClient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Speech from 'expo-speech';

// Fallback icons using text for now
const MicIcon = () => <Text style={{fontSize: 20}}>🎤</Text>;
const SendIcon = () => <Text style={{fontSize: 20}}>📤</Text>;
const SettingsIcon = () => <Text style={{fontSize: 20}}>⚙️</Text>;
const StopIcon = () => <Text style={{fontSize: 20}}>⏹️</Text>;

export default function ChatScreen() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    initSession();
    
    // Set up speech recognition listeners
    let removeListener: any = null;
    import('expo-speech-recognition').then(({ useSpeechRecognitionEvent }) => {
       removeListener = useSpeechRecognitionEvent('result', (event) => {
         if (event.results[0]?.transcript) {
           setInputText(event.results[0].transcript);
         }
       });
    }).catch(() => {});
    
    return () => {
      helios.disconnectWebSocket();
      if (removeListener) removeListener();
    };
  }, []);

  const initSession = async () => {
    const url = await helios.getServerUrl();
    if (!url) {
      router.push('/settings');
      return;
    }

    try {
      const sessions = await helios.fetchSessions();
      let activeSessionId = null;
      if (sessions.length > 0) {
        activeSessionId = sessions[0].id;
      } else {
        // Create new session logic if backend supports it, for now we will just use 0 and let backend handle
        activeSessionId = Date.now(); 
      }
      setSessionId(activeSessionId);
      
      const history = await helios.fetchHistory(activeSessionId);
      if (history && history.length > 0) {
        setMessages(history);
      }

      helios.setOnMessage(handleIncomingMessage);
      await helios.connectWebSocket(activeSessionId);
      setIsConnected(true);
      
      // Request speech permissions
      try {
        const { ExpoSpeechRecognitionModule } = await import('expo-speech-recognition');
        await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      } catch (e) {
        console.warn("Speech recognition not supported on this platform", e);
      }
    } catch (e) {
      console.error(e);
      setIsConnected(false);
    }
  };

  const handleIncomingMessage = async (msg: any) => {
    if (msg.type === 'message') {
      const newMsg: ChatMessage = { id: Date.now(), role: 'assistant', content: msg.content };
      setMessages(prev => [...prev, newMsg]);
      setIsGenerating(false);

      const voiceEnabled = await AsyncStorage.getItem('voice_output_enabled');
      if (voiceEnabled === 'true') {
        Speech.speak(msg.content);
      }
    } else if (msg.type === 'chunk') {
      setIsGenerating(true);
      setMessages(prev => {
        const newMsgs = [...prev];
        const lastMsg = newMsgs[newMsgs.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && lastMsg.id === msg.message_id) {
          lastMsg.content += msg.content;
        } else {
          newMsgs.push({ id: msg.message_id || Date.now(), role: 'assistant', content: msg.content });
        }
        return newMsgs;
      });
    } else if (msg.type === 'done') {
      setIsGenerating(false);
    } else if (msg.type === 'error') {
      setIsGenerating(false);
      setMessages(prev => [...prev, { id: Date.now(), role: 'system', content: `Error: ${msg.content}` }]);
    }
  };

  const sendMessage = async () => {
    if (!inputText.trim() || !sessionId) return;
    
    const newMsg: ChatMessage = { id: Date.now(), role: 'user', content: inputText };
    setMessages(prev => [...prev, newMsg]);
    setInputText('');
    setIsGenerating(true);

    try {
      await helios.sendMessage(sessionId, newMsg.content);
    } catch (e) {
      console.error("Send error", e);
      setIsGenerating(false);
    }
  };

  const stopGeneration = async () => {
    if (sessionId) {
      await helios.sendStop(sessionId);
      setIsGenerating(false);
      Speech.stop();
    }
  };

  const toggleRecording = async () => {
    try {
      const { ExpoSpeechRecognitionModule } = await import('expo-speech-recognition');
      if (isRecording) {
        ExpoSpeechRecognitionModule.stop();
        setIsRecording(false);
        sendMessage(); // Automatically send after stopping
      } else {
        setInputText('');
        ExpoSpeechRecognitionModule.start({ lang: 'en-US' });
        setIsRecording(true);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const renderItem = ({ item }: { item: ChatMessage }) => {
    const isUser = item.role === 'user';
    return (
      <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        <Text style={styles.messageText}>{item.content}</Text>
      </View>
    );
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <View style={styles.header}>
        <Text style={styles.headerTitle}>HELIOS</Text>
        <View style={{flexDirection: 'row', alignItems: 'center'}}>
          <View style={[styles.statusDot, { backgroundColor: isConnected ? '#4CAF50' : '#F44336' }]} />
          <TouchableOpacity onPress={() => router.push('/settings')} style={{marginLeft: 15}}>
            <SettingsIcon />
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        ref={flatListRef}
        data={messages}
        keyExtractor={item => item.id.toString()}
        renderItem={renderItem}
        contentContainerStyle={styles.listContainer}
        onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
      />

      <View style={styles.inputContainer}>
        {isGenerating ? (
          <TouchableOpacity style={styles.stopButton} onPress={stopGeneration}>
            <StopIcon />
            <Text style={{color: 'white', marginLeft: 8}}>Stop Generating</Text>
          </TouchableOpacity>
        ) : (
          <>
            <TouchableOpacity 
              style={[styles.micButton, isRecording && { backgroundColor: '#F44336', borderRadius: 25 }]} 
              onPress={toggleRecording}
            >
              <MicIcon />
            </TouchableOpacity>
            
            <TextInput
              style={styles.input}
              value={inputText}
              onChangeText={setInputText}
              placeholder="Message HELIOS..."
              placeholderTextColor="#888"
              multiline
            />

            <TouchableOpacity style={styles.sendButton} onPress={sendMessage}>
              <SendIcon />
            </TouchableOpacity>
          </>
        )}
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 15,
    paddingTop: 50,
    backgroundColor: '#0a0e1a',
    borderBottomWidth: 1,
    borderBottomColor: '#1e2d4a',
  },
  headerTitle: {
    color: '#14b8a6', // Cyan accent
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 2,
  },
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    shadowColor: '#14b8a6',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.8,
    shadowRadius: 5,
    elevation: 3,
  },
  listContainer: {
    padding: 15,
    paddingBottom: 20,
  },
  messageBubble: {
    maxWidth: '85%',
    padding: 14,
    borderRadius: 12,
    marginBottom: 12,
  },
  userBubble: {
    backgroundColor: '#8b5cf6', // Purple accent
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
    shadowColor: '#8b5cf6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 5,
  },
  assistantBubble: {
    backgroundColor: '#1a2236', // Card background
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#1e2d4a',
  },
  messageText: {
    color: '#f1f5f9',
    fontSize: 16,
    lineHeight: 24,
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    backgroundColor: '#0f1629',
    borderTopWidth: 1,
    borderTopColor: '#1e2d4a',
  },
  input: {
    flex: 1,
    backgroundColor: '#1a2236',
    color: '#f1f5f9',
    borderRadius: 20,
    paddingHorizontal: 18,
    paddingVertical: 12,
    maxHeight: 100,
    fontSize: 16,
    borderWidth: 1,
    borderColor: '#1e2d4a',
  },
  micButton: {
    padding: 12,
    marginRight: 8,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButton: {
    padding: 12,
    marginLeft: 8,
    backgroundColor: '#14b8a6',
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#14b8a6',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.5,
    shadowRadius: 4,
    elevation: 3,
  },
  stopButton: {
    flex: 1,
    flexDirection: 'row',
    backgroundColor: '#ef4444', // Red accent
    padding: 15,
    borderRadius: 12,
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#ef4444',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 5,
  }
});

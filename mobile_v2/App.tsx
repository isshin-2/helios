import { StatusBar } from 'expo-status-bar';
import React, { useState, useEffect, useRef } from 'react';
import { StyleSheet, Text, View, TextInput, TouchableOpacity, ScrollView, SafeAreaView, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import * as DocumentPicker from 'expo-document-picker';
import { HeliosClient } from './src/api/client';

export default function App() {
  const [messages, setMessages] = useState<{role: string, content: string}[]>([]);
  const [input, setInput] = useState('');
  const [status, setStatus] = useState('Initializing...');
  const [isOffline, setIsOffline] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [localModelLoaded, setLocalModelLoaded] = useState(false);
  
  // We use a ref to persist the client instance
  const clientRef = useRef<HeliosClient | null>(null);
  const scrollViewRef = useRef<ScrollView>(null);

  useEffect(() => {
    clientRef.current = new HeliosClient((msg) => {
      if (msg.type === 'status') {
        setStatus(msg.text);
      } else if (msg.type === 'chunk') {
        setMessages(prev => {
          const last = prev[prev.length - 1];
          if (last && last.role === 'assistant') {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1] = { ...last, content: last.content + msg.content };
            return newMessages;
          } else {
            return [...prev, { role: 'assistant', content: msg.content }];
          }
        });
      } else if (msg.type === 'done') {
        setIsGenerating(false);
        setStatus('Ready');
      }
    });

    // Simple polling to update offline state UI
    const interval = setInterval(() => {
      if (clientRef.current) {
        setIsOffline(clientRef.current.isOffline);
        if (clientRef.current.isOffline && !localModelLoaded && !isGenerating) {
            setStatus("Offline. Please load a local GGUF model.");
        } else if (!clientRef.current.isOffline && !isGenerating) {
            setStatus("Online. Connected to HELIOS Backend.");
        }
      }
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const sendMessage = () => {
    if (!input.trim() || !clientRef.current || isGenerating) return;

    setMessages(prev => [...prev, { role: 'user', content: input }]);
    setIsGenerating(true);
    setStatus('Generating...');
    clientRef.current.sendMessage(input);
    setInput('');
  };

  const loadLocalModel = async () => {
    try {
      setStatus("Selecting model file...");
      const res = await DocumentPicker.getDocumentAsync({
        copyToCacheDirectory: true,
      });
      if (!res.canceled && res.assets && res.assets.length > 0 && clientRef.current) {
        setStatus("Loading local model (this may take a moment)...");
        let realPath = res.assets[0].uri;
        // C++ cannot read 'file://' prefixed paths
        if (realPath.startsWith('file://')) {
            realPath = realPath.replace('file://', '');
        }
        await clientRef.current.setupOfflineModel(realPath);
        setLocalModelLoaded(true);
        setStatus("Local model loaded successfully!");
      } else {
        setStatus("Model selection cancelled.");
      }
    } catch (err) {
      setStatus("Failed to load local model.");
      console.error(err);
    }
  };

  return (
    <SafeAreaView style={styles.safeArea}>
      <KeyboardAvoidingView 
        style={styles.container} 
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <View style={styles.header}>
          <Text style={styles.headerTitle}>HELIOS Mobile</Text>
          <View style={[styles.badge, isOffline ? styles.badgeOffline : styles.badgeOnline]}>
            <Text style={styles.badgeText}>{isOffline ? 'OFFLINE' : 'ONLINE'}</Text>
          </View>
        </View>

        {isOffline && !localModelLoaded && (
          <TouchableOpacity style={styles.loadModelBtn} onPress={loadLocalModel}>
            <Text style={styles.loadModelBtnText}>Load Local GGUF Model (Offline Mode)</Text>
          </TouchableOpacity>
        )}

        <ScrollView 
          style={styles.chatArea} 
          ref={scrollViewRef}
          onContentSizeChange={() => scrollViewRef.current?.scrollToEnd({ animated: true })}
        >
          {messages.map((msg, idx) => (
            <View key={idx} style={[styles.messageBubble, msg.role === 'user' ? styles.userBubble : styles.botBubble]}>
              <Text style={[styles.messageText, msg.role === 'user' ? styles.userText : styles.botText]}>
                {msg.content}
              </Text>
            </View>
          ))}
          {isGenerating && (
            <View style={[styles.messageBubble, styles.botBubble]}>
               <ActivityIndicator color="#000" size="small" />
            </View>
          )}
        </ScrollView>

        <View style={styles.statusContainer}>
          <Text style={styles.statusText}>{status}</Text>
        </View>

        <View style={styles.inputArea}>
          <TextInput 
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Type your message..."
            placeholderTextColor="#888"
            onSubmitEditing={sendMessage}
          />
          <TouchableOpacity 
            style={[styles.sendBtn, (!input.trim() || isGenerating) && styles.sendBtnDisabled]} 
            onPress={sendMessage}
            disabled={!input.trim() || isGenerating}
          >
            <Text style={styles.sendBtnText}>Send</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
      <StatusBar style="dark" />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: '#f5f5f5' },
  container: { flex: 1 },
  header: {
    padding: 16,
    paddingTop: Platform.OS === 'android' ? 40 : 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderColor: '#eee',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  headerTitle: { fontSize: 20, fontWeight: 'bold' },
  badge: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  badgeOnline: { backgroundColor: '#e6f4ea' },
  badgeOffline: { backgroundColor: '#fce8e6' },
  badgeText: { fontSize: 12, fontWeight: 'bold', color: '#555' },
  loadModelBtn: {
    backgroundColor: '#ff9800',
    margin: 16,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  loadModelBtnText: { color: '#fff', fontWeight: 'bold' },
  chatArea: { flex: 1, padding: 16 },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
    marginBottom: 10,
  },
  userBubble: {
    backgroundColor: '#007aff',
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
  botBubble: {
    backgroundColor: '#fff',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#eee',
  },
  messageText: { fontSize: 16 },
  userText: { color: '#fff' },
  botText: { color: '#333' },
  statusContainer: { paddingHorizontal: 16, paddingVertical: 4 },
  statusText: { fontSize: 12, color: '#888', fontStyle: 'italic' },
  inputArea: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: '#fff',
    borderTopWidth: 1,
    borderColor: '#eee',
  },
  textInput: {
    flex: 1,
    backgroundColor: '#f0f0f0',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 16,
    maxHeight: 100,
  },
  sendBtn: {
    marginLeft: 12,
    backgroundColor: '#007aff',
    borderRadius: 20,
    paddingHorizontal: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnDisabled: { backgroundColor: '#b0c4de' },
  sendBtnText: { color: '#fff', fontWeight: 'bold', fontSize: 16 },
});

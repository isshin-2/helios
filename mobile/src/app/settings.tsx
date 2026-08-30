import React, { useState, useEffect } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, Switch } from 'react-native';
import { helios } from '../services/HeliosClient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { router } from 'expo-router';

export default function SettingsScreen() {
  const [url, setUrl] = useState('');
  const [voiceOutput, setVoiceOutput] = useState(false);

  useEffect(() => {
    helios.getServerUrl().then(val => setUrl(val));
    AsyncStorage.getItem('voice_output_enabled').then(val => {
      setVoiceOutput(val === 'true');
    });
  }, []);

  const handleSave = async () => {
    try {
      if (!url.startsWith('http')) {
        Alert.alert("Invalid URL", "Must start with http:// or https://");
        return;
      }
      await helios.setServerUrl(url);
      await AsyncStorage.setItem('voice_output_enabled', voiceOutput ? 'true' : 'false');
      Alert.alert("Saved", "Settings updated successfully.");
      router.back();
    } catch (e) {
      Alert.alert("Error", "Could not save settings.");
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.header}>HELIOS Settings</Text>
      
      <Text style={styles.label}>Server URL (e.g. http://192.168.1.10:8000)</Text>
      <TextInput
        style={styles.input}
        value={url}
        onChangeText={setUrl}
        placeholder="http://..."
        placeholderTextColor="#666"
        autoCapitalize="none"
        keyboardType="url"
      />

      <View style={styles.switchContainer}>
        <Text style={styles.label}>Enable Voice Output (TTS)</Text>
        <Switch 
          value={voiceOutput} 
          onValueChange={setVoiceOutput} 
          trackColor={{ false: "#333", true: "#007BFF" }}
        />
      </View>

      <TouchableOpacity style={styles.saveButton} onPress={handleSave}>
        <Text style={styles.saveButtonText}>Save & Connect</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0a0e1a',
    padding: 20,
    justifyContent: 'center',
  },
  header: {
    color: '#14b8a6', // Cyan accent
    fontSize: 26,
    fontWeight: '900',
    letterSpacing: 2,
    marginBottom: 40,
    textAlign: 'center',
  },
  label: {
    color: '#94a3b8',
    fontSize: 14,
    marginBottom: 10,
    fontWeight: '600',
  },
  input: {
    backgroundColor: '#1a2236',
    color: '#f1f5f9',
    borderRadius: 12,
    padding: 16,
    fontSize: 16,
    marginBottom: 30,
    borderWidth: 1,
    borderColor: '#1e2d4a',
  },
  switchContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 40,
    backgroundColor: '#1a2236',
    padding: 20,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#1e2d4a',
  },
  saveButton: {
    backgroundColor: '#8b5cf6', // Purple accent
    padding: 18,
    borderRadius: 12,
    alignItems: 'center',
    shadowColor: '#8b5cf6',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 5,
  },
  saveButtonText: {
    color: '#FFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  }
});

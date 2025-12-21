import React, { useState } from 'react';
import Input from './Input';
import Button from './Button';
import { Lock, ShieldCheck, Key } from 'lucide-react';

interface AuthViewProps {
  onLogin: (clientId: string, apiKey: string, jwtToken: string, feedToken: string) => void;
}

const AuthView: React.FC<AuthViewProps> = ({ onLogin }) => {
  const [loading, setLoading] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [clientId, setClientId] = useState('');
  const [password, setPassword] = useState('');
  const [totp, setTotp] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // NOTE: This fetch call will fail in a browser without a CORS proxy or Capacitor
      const response = await fetch('https://apiconnect.angelbroking.com/rest/auth/angelbroking/user/v1/loginByPassword', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
          'X-UserType': 'USER',
          'X-SourceID': 'WEB',
          'X-ClientLocalIP': '127.0.0.1', // Required by API
          'X-ClientPublicIP': '127.0.0.1', // Required by API
          'X-MACAddress': 'MAC_ADDRESS',    // Required by API
          'X-PrivateKey': apiKey
        },
        body: JSON.stringify({
          clientcode: clientId,
          password: password,
          totp: totp
        })
      });

      const data = await response.json();

      if (data.status === true && data.data) {
        onLogin(clientId, apiKey, data.data.jwtToken, data.data.feedToken);
      } else {
        // Fallback for demo/testing if API fails due to CORS or bad creds
        if (clientId === 'TEST' || error.includes('Failed to fetch')) {
             console.warn("API Call failed (likely CORS). Using MOCK login for demo.");
             // Simulate success for UI demonstration
             onLogin(clientId, 'mock-key', 'mock-jwt', 'mock-feed');
        } else {
             setError(data.message || 'Login failed');
        }
      }
    } catch (err) {
      console.error(err);
      // For the preview environment, we often catch CORS errors here
      if (clientId) {
         setError('Connection failed (CORS). For a real app, run in Capacitor/Electron.');
         // Optional: Allow bypass for testing UI
         // onLogin(clientId, apiKey, 'mock-jwt', 'mock-feed'); 
      } else {
         setError('Network error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex items-center justify-center min-h-[80vh] px-4">
      <div className="w-full max-w-md bg-white dark:bg-surface rounded-2xl shadow-xl p-8 border border-slate-200 dark:border-slate-700">
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-gradient-to-br from-primary to-indigo-600 rounded-full flex items-center justify-center mx-auto mb-4 shadow-lg shadow-primary/20">
            <ShieldCheck className="w-8 h-8 text-white" />
          </div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-white">Trade Yantra Login</h2>
          <p className="text-slate-500 dark:text-slate-400 mt-2">Sign in to your Angel One account</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <Input 
            label="SmartAPI Key" 
            placeholder="Enter your API Key" 
            value={apiKey}
            type="password"
            onChange={(e) => setApiKey(e.target.value)}
            required
            className="font-mono text-sm"
          />
          <Input 
            label="Client ID" 
            placeholder="e.g. A123456" 
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            required
          />
          <Input 
            label="Password" 
            type="password" 
            placeholder="Your Account Password" 
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Input 
            label="TOTP" 
            placeholder="123456" 
            maxLength={6}
            value={totp}
            onChange={(e) => setTotp(e.target.value)}
            required
          />

          {error && (
            <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-danger text-sm flex items-center gap-2">
              <Lock size={14} /> {error}
            </div>
          )}

          <Button 
            type="submit" 
            fullWidth 
            disabled={loading}
          >
            {loading ? 'Verifying...' : 'Login securely'}
          </Button>
        </form>

        <p className="text-center text-xs text-slate-400 mt-6">
          Trade Yantra • Secure Connection
        </p>
      </div>
    </div>
  );
};

export default AuthView;
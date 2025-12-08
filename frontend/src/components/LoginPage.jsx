import { useState } from 'react';
import { login, API_BASE_URL } from '../services/api';

function LoginPage({ onLoginSuccess }) {
    // ... state ...

    // ... handleInputChange ...

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        try {
            const response = await login(
                formData.apiKey,
                formData.clientId,
                formData.password,
                formData.totpSecret
            );

            // Store session and notify parent
            onLoginSuccess({
                sessionId: response.session_id,
                clientId: response.client_id,
            });
        } catch (err) {
            console.error('Login error:', err);
            // Show specific error if available, otherwise show network error or default
            let errorMessage = err.response?.data?.detail || err.message || 'Login failed. Please check your credentials.';

            // Add API URL to error for debugging
            if (!err.response) {
                errorMessage += ` (Server: ${API_BASE_URL})`;
            }

            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0A0E27] flex items-center justify-center p-4">
            <div className="w-full max-w-md">
                <div className="text-center mb-8">
                    <h1 className="text-4xl font-bold text-[#667EEA] mb-2">Trade Yantra</h1>
                    <p className="text-gray-400">Smart Trading Alerts</p>
                </div>

                <form onSubmit={handleSubmit} className="bg-[#222844] rounded-lg p-6 border border-[#2D3748]">
                    <div className="space-y-4">
                        {/* API Key */}
                        <div>
                            <label className="block text-gray-300 text-sm font-medium mb-2">
                                SmartAPI Key
                            </label>
                            <input
                                type="text"
                                name="apiKey"
                                value={formData.apiKey}
                                onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-[#0A0E27] border border-[#2D3748] rounded-lg text-white focus:outline-none focus:border-[#667EEA]"
                                placeholder="Enter your API key"
                                required
                            />
                        </div>

                        {/* Client ID */}
                        <div>
                            <label className="block text-gray-300 text-sm font-medium mb-2">
                                Client ID
                            </label>
                            <input
                                type="text"
                                name="clientId"
                                value={formData.clientId}
                                onChange={handleInputChange}
                                className="w-full px-4 py-2 bg-[#0A0E27] border border-[#2D3748] rounded-lg text-white focus:outline-none focus:border-[#667EEA]"
                                placeholder="Enter your client ID"
                                required
                            />
                        </div>

                        {/* Password */}
                        <div>
                            <label className="block text-gray-300 text-sm font-medium mb-2">
                                Password
                            </label>
                            <div className="relative">
                                <input
                                    type={showPassword ? 'text' : 'password'}
                                    name="password"
                                    value={formData.password}
                                    onChange={handleInputChange}
                                    className="w-full px-4 py-2 bg-[#0A0E27] border border-[#2D3748] rounded-lg text-white focus:outline-none focus:border-[#667EEA]"
                                    placeholder="Enter your password"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword(!showPassword)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                                >
                                    {showPassword ? '🙈' : '👁️'}
                                </button>
                            </div>
                        </div>

                        {/* TOTP Secret */}
                        <div>
                            <label className="block text-gray-300 text-sm font-medium mb-2">
                                TOTP Secret
                            </label>
                            <div className="relative">
                                <input
                                    type={showTotp ? 'text' : 'password'}
                                    name="totpSecret"
                                    value={formData.totpSecret}
                                    onChange={handleInputChange}
                                    className="w-full px-4 py-2 bg-[#0A0E27] border border-[#2D3748] rounded-lg text-white focus:outline-none focus:border-[#667EEA]"
                                    placeholder="Enter your TOTP secret"
                                    required
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowTotp(!showTotp)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
                                >
                                    {showTotp ? '🙈' : '👁️'}
                                </button>
                            </div>
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="bg-red-500/10 border border-red-500 rounded-lg p-3">
                                <p className="text-red-400 text-sm">{error}</p>
                            </div>
                        )}

                        {/* Submit Button */}
                        <button
                            type="submit"
                            disabled={loading}
                            className="w-full bg-[#667EEA] hover:bg-[#5568D3] text-white font-medium py-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loading ? (
                                <span className="flex items-center justify-center">
                                    <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    Logging in...
                                </span>
                            ) : (
                                'Login'
                            )}
                        </button>
                    </div>
                </form>

                <p className="text-center text-gray-500 text-sm mt-6">
                    Credentials are never stored • Session-based authentication
                </p>
            </div>
        </div>
    );
}

export default LoginPage;

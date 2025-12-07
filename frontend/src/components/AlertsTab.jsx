import { useState } from 'react';
import { generateAlerts, deleteAlert, pauseAlerts } from '../services/api';

function AlertsTab({ sessionId, alerts, setAlerts, isPaused, setIsPaused }) {
    const [generating, setGenerating] = useState(false);

    const handleGenerateAlerts = async () => {
        try {
            setGenerating(true);
            const response = await generateAlerts(sessionId);
            // Alerts will be updated via parent state
            alert(`Generated ${response.count || 0} alerts`);
        } catch (err) {
            console.error('Generate alerts error:', err);
            alert(err.response?.data?.detail || 'Failed to generate alerts');
        } finally {
            setGenerating(false);
        }
    };

    const handleDeleteAlert = async (alertId) => {
        try {
            await deleteAlert(sessionId, alertId);
            setAlerts(alerts.filter(a => a.id !== alertId));
        } catch (err) {
            console.error('Delete alert error:', err);
        }
    };

    const handleTogglePause = async (newValue) => {
        try {
            await pauseAlerts(sessionId, newValue);
            setIsPaused(newValue);
        } catch (err) {
            console.error('Pause alerts error:', err);
        }
    };

    return (
        <div className="max-w-4xl mx-auto space-y-4">
            {/* Controls */}
            <div className="bg-[#222844] rounded-lg p-4 border border-[#2D3748]">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h3 className="text-white font-bold text-lg">3-6-9 Alert Strategy</h3>
                        <p className="text-gray-400 text-sm">Auto-generate support/resistance levels</p>
                    </div>
                    <button
                        onClick={handleGenerateAlerts}
                        disabled={generating}
                        className="px-4 py-2 bg-[#667EEA] hover:bg-[#5568D3] text-white rounded-lg transition-colors disabled:opacity-50"
                    >
                        {generating ? 'Generating...' : '⚡ Generate Levels'}
                    </button>
                </div>

                {/* Pause Switch */}
                <div className="flex items-center justify-between pt-3 border-t border-[#2D3748]">
                    <span className="text-gray-300 text-sm font-medium">Pause Monitoring</span>
                    <button
                        onClick={() => handleTogglePause(!isPaused)}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isPaused ? 'bg-[#F56565]' : 'bg-[#48BB78]'
                            }`}
                    >
                        <span
                            className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${isPaused ? 'translate-x-6' : 'translate-x-1'
                                }`}
                        />
                    </button>
                </div>
            </div>

            {/* Active Alerts */}
            <div className="space-y-3">
                <h3 className="text-white font-bold text-lg">Active Alerts ({alerts.length})</h3>

                {alerts.length === 0 ? (
                    <div className="bg-[#222844] rounded-lg p-8 border border-[#2D3748] text-center">
                        <p className="text-gray-400">No active alerts. Click "Generate Levels" to create 3-6-9 alerts.</p>
                    </div>
                ) : (
                    alerts.map((alert) => {
                        const isAbove = alert.condition === 'ABOVE';
                        const color = isAbove ? '#48BB78' : '#F56565';
                        const icon = isAbove ? '📈' : '📉';

                        return (
                            <div
                                key={alert.id}
                                className="bg-[#222844] rounded-lg p-4 border border-[#2D3748] hover:border-[#667EEA] transition-colors"
                                style={{ borderLeftWidth: '4px', borderLeftColor: color }}
                            >
                                <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-3">
                                        <span className="text-2xl">{icon}</span>
                                        <div>
                                            <h4 className="text-white font-bold">{alert.symbol}</h4>
                                            <p className="text-gray-400 text-sm">
                                                Target: <span className="font-mono" style={{ color }}>₹{alert.price?.toFixed(2)}</span>
                                                {' '} • {alert.condition}
                                            </p>
                                        </div>
                                    </div>
                                    <button
                                        onClick={() => handleDeleteAlert(alert.id)}
                                        className="px-3 py-1.5 bg-[#F56565] hover:bg-red-600 text-white text-sm rounded-lg transition-colors"
                                    >
                                        Delete
                                    </button>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}

export default AlertsTab;

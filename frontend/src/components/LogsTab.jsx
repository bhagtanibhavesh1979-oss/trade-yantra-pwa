function LogsTab({ logs }) {
    return (
        <div className="max-w-4xl mx-auto">
            <div className="bg-[#222844] rounded-lg border border-[#2D3748] overflow-hidden">
                <div className="bg-[#1A1F3A] px-4 py-3 border-b border-[#2D3748]">
                    <h3 className="text-white font-bold">Activity Log</h3>
                </div>

                <div className="divide-y divide-[#2D3748] max-h-[600px] overflow-y-auto">
                    {logs.length === 0 ? (
                        <div className="p-8 text-center">
                            <p className="text-gray-400">No activity yet. Alerts will appear here when triggered.</p>
                        </div>
                    ) : (
                        logs.map((log, index) => (
                            <div
                                key={index}
                                className="px-4 py-3 hover:bg-[#2D3748] transition-colors"
                            >
                                <div className="flex items-start gap-3">
                                    <span className="text-xs text-gray-500 font-mono w-16 flex-shrink-0">
                                        {log.time}
                                    </span>
                                    <span className="text-sm font-bold text-[#667EEA] w-32 flex-shrink-0">
                                        {log.symbol}
                                    </span>
                                    <p className="text-sm text-gray-300 flex-1">
                                        {log.msg}
                                    </p>
                                </div>
                            </div>
                        ))
                    )}
                </div>
            </div>
        </div>
    );
}

export default LogsTab;

import React, { useEffect, useRef } from 'react';

const TradingViewChart = ({ symbol, height = '100%', theme = 'dark' }) => {
    const container = useRef();

    useEffect(() => {
        if (!container.current) return;

        // Clear previous content
        container.current.innerHTML = '';

        // Create the widget script element
        const script = document.createElement("script");
        script.src = "https://s3.tradingview.com/external-embedding/embed-widget-symbol-overview.js";
        script.type = "text/javascript";
        script.async = true;

        // Clean and prepare the symbol
        let cleanSymbol = symbol;
        if (cleanSymbol.includes(':')) {
            const parts = cleanSymbol.split(':');
            const exch = parts[0];
            const sym = parts[1].replace('-EQ', '');
            cleanSymbol = `${exch}:${sym}`;
        } else {
            cleanSymbol = `NSE:${cleanSymbol.replace('-EQ', '')}`;
        }

        // Configuration for the "Symbol Overview" widget which is much more stable on localhost
        const config = {
            "symbols": [
                [
                    cleanSymbol,
                    cleanSymbol
                ]
            ],
            "chartOnly": true,
            "width": "100%",
            "height": "100%",
            "locale": "in",
            "colorTheme": theme,
            "autosize": true,
            "showVolume": false,
            "showMA": false,
            "hideDateRanges": false,
            "hideMarketStatus": true,
            "hideSymbolLogo": true,
            "scalePosition": "right",
            "scaleMode": "Normal",
            "fontFamily": "-apple-system, BlinkMacSystemFont, Trebuchet MS, Roboto, Ubuntu, sans-serif",
            "fontSize": "10",
            "noTimeScale": false,
            "valuesTracking": "1",
            "changeMode": "price-and-percent",
            "chartType": "area",
            "maLineColor": "#2962FF",
            "maLineWidth": 1,
            "maLength": 9,
            "lineWidth": 2,
            "lineColor": "#2962FF",
            "topColor": "rgba(41, 98, 255, 0.3)",
            "bottomColor": "rgba(41, 98, 255, 0)",
            "dateFormat": "MMM dd, yyyy",
            "timeHoursFormat": "24-h"
        };

        script.innerHTML = JSON.stringify(config);
        container.current.appendChild(script);

        return () => {
            if (container.current) {
                container.current.innerHTML = '';
            }
        };
    }, [symbol, theme]);

    return (
        <div
            ref={container}
            className="tradingview-widget-container"
            style={{ height, width: "100%", minHeight: "200px" }}
        >
            <div className="tradingview-widget-container__widget"></div>
        </div>
    );
};

export default TradingViewChart;

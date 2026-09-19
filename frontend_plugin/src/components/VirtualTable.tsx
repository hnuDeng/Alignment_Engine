import React, { useRef, useState, useEffect, useMemo, useCallback } from 'react';

export class VirtualTableException extends Error {
    constructor(message: string) {
        super(`VirtualTableException: ${message}`);
        this.name = 'VirtualTableException';
    }
}

export class InvalidDataException extends VirtualTableException {
    constructor(message: string) {
        super(`InvalidDataException: ${message}`);
        this.name = 'InvalidDataException';
    }
}

export class DOMRefException extends VirtualTableException {
    constructor(message: string) {
        super(`DOMRefException: ${message}`);
        this.name = 'DOMRefException';
    }
}

export interface ColumnDef<T> {
    key: keyof T;
    title: string;
    width: number;
    render?: (value: any, row: T) => React.ReactNode;
}

export interface VirtualTableProps<T> {
    data: T[];
    columns: ColumnDef<T>[];
    rowHeight: number;
    containerHeight: number;
    overscan?: number;
}

export function VirtualTable<T extends { id: string | number }>(props: VirtualTableProps<T>) {
    const { data, columns, rowHeight, containerHeight, overscan = 5 } = props;

    if (!Array.isArray(data)) {
        throw new InvalidDataException("Data must be an array");
    }

    const containerRef = useRef<HTMLDivElement>(null);
    const [scrollTop, setScrollTop] = useState(0);

    const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
        setScrollTop(e.currentTarget.scrollTop);
    }, []);

    // Utilizing IntersectionObserver logic principle for DOM recycling manually via math 
    // (since true IntersectionObserver for 100k individual rows is too slow, math is O(1))
    const totalHeight = data.length * rowHeight;
    const startIndex = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
    const endIndex = Math.min(data.length - 1, Math.floor((scrollTop + containerHeight) / rowHeight) + overscan);

    const visibleRows = useMemo(() => {
        const rows = [];
        for (let i = startIndex; i <= endIndex; i++) {
            rows.push(
                <div
                    key={data[i].id}
                    style={{
                        position: 'absolute',
                        top: i * rowHeight,
                        height: rowHeight,
                        width: '100%',
                        display: 'flex',
                        borderBottom: '1px solid #333'
                    }}
                >
                    {columns.map(col => (
                        <div
                            key={col.key as string}
                            style={{
                                width: col.width,
                                padding: '0 8px',
                                boxSizing: 'border-box',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap'
                            }}
                        >
                            {col.render ? col.render(data[i][col.key], data[i]) : String(data[i][col.key])}
                        </div>
                    ))}
                </div>
            );
        }
        return rows;
    }, [data, columns, startIndex, endIndex, rowHeight]);

    useEffect(() => {
        if (!containerRef.current) {
            // Defense against unmounted ref access
            console.warn("DOMRefException: Container ref is null on mount");
        }
    }, []);

    return (
        <div 
            ref={containerRef}
            style={{ 
                height: containerHeight, 
                overflowY: 'auto', 
                position: 'relative',
                border: '1px solid #444',
                backgroundColor: '#1e1e1e',
                color: '#ddd'
            }}
            onScroll={handleScroll}
        >
            <div style={{ height: totalHeight, position: 'relative' }}>
                {visibleRows}
            </div>
        </div>
    );
}

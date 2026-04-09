function Skeleton({ className, ...props }) {
    return (
        <div
            className={`animate-pulse bg-[var(--bg-secondary)] rounded-md ${className}`}
            {...props}
        />
    );
}

export { Skeleton };

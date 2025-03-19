# Name: MatPlotLib Line Plot
# Description: This is an example of using MatPlotLib to create a line plot with one or more series.
# python_version: >=3.8
# inclusion_criteria: If you are creating plots, this codeblock is likely to be useful.
# exclusion_criteria: If you are not creating any plots, this codeblock is unlikely to be useful.
# pip_requirement: matplotlib
# pip_requirement: numpy

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

matplotlib.use("Agg")  # ABSOLUTELY REQUIRED OR THE CODE WILL SILENTLY FREEZE AND COST A LOT OF MONEY: Use the Agg backend for headless environments

def plot_multiple_series(series_list, x_key='x', y_key='y', labels=None, title=None, xlabel=None, ylabel=None, filename=None):
    """
    Plots multiple series on the same line plot, with different colors for each series.
    Optionally saves the plot to a PDF file if a filename is provided.

    Parameters:
    series_list (list of lists of dictionaries): A list containing the series to plot. Each series is a list of dictionaries with data points.
    x_key (string, optional): The key used for the x-values in the dictionaries.
    y_key (string, optional): The key used for the y-values in the dictionaries.
    labels (list of strings, optional): Labels for each series.
    title (string, optional): Title of the plot.
    xlabel (string, optional): Label for the x-axis.
    ylabel (string, optional): Label for the y-axis.
    filename (string, optional): If provided, saves the plot to the given filename (should end with .pdf). If not provided, displays the plot.
    """
    num_series = len(series_list)
    colors = plt.cm.viridis(np.linspace(0, 1, num_series))

    plt.figure()  # Create a new figure

    for idx, series in enumerate(series_list):
        x_values = [point[x_key] for point in series]
        y_values = [point[y_key] for point in series]
        plt.plot(x_values, y_values, color=colors[idx], label=labels[idx] if labels else None)
    if labels is not None:
        plt.legend()
    if title is not None:
        plt.title(title)
    if xlabel is not None:
        plt.xlabel(xlabel)
    else:
        plt.xlabel(x_key)
    if ylabel is not None:
        plt.ylabel(ylabel)
    else:
        plt.ylabel(y_key)
    plt.tight_layout()  # Adjust layout to prevent clipping of labels

    if (filename is not None):
        # If a filename is provided, save the plot to a PDF file
        plt.savefig(filename, format='pdf')
        plt.close()
        print(f"Plot saved as {filename}")
    else:
        # Otherwise, if no filename is providede, display the plot to the user
        plt.show()


# An example (3 series, custom keys, shown on screen)
def example1():
    # Sample data with custom keys 'time' and 'value'
    series1 = [{'time': 0, 'value': 1}, {'time': 1, 'value': 3}, {'time': 2, 'value': 2}, {'time': 3, 'value': 4}, {'time': 4, 'value': 5}]
    series2 = [{'time': 0, 'value': 2}, {'time': 1, 'value': 2}, {'time': 2, 'value': 3}, {'time': 3, 'value': 3}, {'time': 4, 'value': 4}]
    series3 = [{'time': 0, 'value': 5}, {'time': 1, 'value': 3}, {'time': 2, 'value': 4}, {'time': 3, 'value': 2}, {'time': 4, 'value': 1}]

    # Labels for each series
    labels = ['Series A', 'Series B', 'Series C']

    # Plotting the series with custom keys
    plot_multiple_series(
        series_list=[series1, series2, series3],
        x_key='time',
        y_key='value',
        labels=labels,
        title='Multiple Series Plot with Custom Keys',
        xlabel='Time',
        ylabel='Value',
        filename=None       # Show the plot to the user (do not provide a filename)
    )


# An example (2 series, generated with numerical functions, saved to file)
def example2():
    # Generate data for sine and cosine waves
    x_values = np.linspace(0, 2 * np.pi, 100)  # 100 points from 0 to 2π
    sine_values = np.sin(x_values)
    cosine_values = np.cos(x_values)

    # Prepare the data in the required format (list of dictionaries with 'x' and 'y' keys)
    sine_series = [{'x': x, 'y': y} for x, y in zip(x_values, sine_values)]
    cosine_series = [{'x': x, 'y': y} for x, y in zip(x_values, cosine_values)]

    # Labels for the series
    labels = ['Sine Wave', 'Cosine Wave']

    # Plot the series and save to 'sine_cosine_plot.pdf'
    plot_multiple_series(
        series_list=[sine_series, cosine_series],
        x_key='x',
        y_key='y',
        labels=labels,
        title='Sine and Cosine Waves',
        xlabel='Angle (radians)',
        ylabel='Amplitude',
        filename='sine_cosine_plot.pdf'  # Specify the filename to save the plot
    )


# Main
if __name__ == "__main__":
    example1()
    example2()
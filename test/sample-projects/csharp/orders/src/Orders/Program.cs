using Orders.Services;
using Orders.Repositories;

namespace Orders;

public static class Program
{
    public static void Main(string[] args)
    {
        var repo = new InMemoryOrderRepository();
        var service = new OrderService(repo);
        service.Create("A100", 2);
        var order = service.MarkPaid("A100");
        Console.WriteLine($"Order {order?.Id} paid={order?.Paid}");
    }
}